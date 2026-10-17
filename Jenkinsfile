// Webhook: notifyCommit via Gitea webhook #4
pipeline {
    agent { label 'agent-45' }  // Docker builds/pushes must run on agent-45 (its daemon trusts the HTTP registry 192.168.1.147:5000)

    options {
        buildDiscarder(logRotator(numToKeepStr: '5'))
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
    }

    environment {
        REGISTRY = "192.168.1.147:5000"
        IMAGE_NAME = "research-agent"
        NO_PROXY = 'localhost,127.0.0.1,192.168.1.0/24,192.168.1.147,192.168.1.62'
        no_proxy = 'localhost,127.0.0.1,192.168.1.0/24,192.168.1.147,192.168.1.62,192.168.1.45'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Image') {
            steps {
                echo 'Building Docker image...'
                sh "docker build -t ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} -t ${REGISTRY}/${IMAGE_NAME}:latest ."
            }
        }

        stage('Lint') {
            steps {
                echo 'Linting with ruff (rules in ruff.toml)...'
                // ruff is not a runtime dependency, so install it into the throwaway container only.
                sh """
                docker run --rm ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} \
                    sh -c "pip install -q --no-warn-script-location ruff==0.15.7 && python -m ruff check src tests mcp_server.py"
                """
            }
        }

        stage('Run Tests') {
            steps {
                echo 'Running unit tests inside built image...'
                script {
                    try {
                        sh """
                        docker run --name test-${BUILD_NUMBER} \
                            -e TAVILY_API_KEY=test-key \
                            ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} \
                            python -m pytest tests/ -v \
                                --cov=src \
                                --cov-report=term \
                                --cov-report=xml:coverage.xml \
                                --cov-fail-under=45 \
                                --junitxml=test-results.xml \
                                --disable-warnings
                        """
                    } finally {
                        sh "docker cp test-${BUILD_NUMBER}:/app/test-results.xml \${WORKSPACE}/test-results.xml || true"
                        sh "docker cp test-${BUILD_NUMBER}:/app/coverage.xml \${WORKSPACE}/coverage.xml || true"
                        sh "docker rm test-${BUILD_NUMBER} || true"
                    }
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'test-results.xml'
                    archiveArtifacts artifacts: 'coverage.xml', allowEmptyArchive: true
                }
            }
        }

        stage('Dependency Audit') {
            steps {
                echo 'Auditing the dependencies installed in the image (a finding marks the build UNSTABLE, it does not block the push)...'
                // Accepted risk: these 4 chromadb advisories affect the ChromaDB *server*
                // (HTTP API, multi-tenant RBAC). The app only uses the embedded PersistentClient,
                // and no fixed release exists. Revisit when chromadb publishes a fix.
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    sh """
                    docker run --rm ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} \
                        sh -c "pip install -q --no-warn-script-location pip-audit && python -m pip_audit --skip-editable \
                            --ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 \
                            --ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815"
                    """
                }
            }
        }

        stage('Push to Registry') {
            steps {
                echo "Pushing image to ${REGISTRY}..."
                retry(3) { sh "DOCKER_CONFIG=/tmp docker push ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}" }
                retry(3) { sh "DOCKER_CONFIG=/tmp docker push ${REGISTRY}/${IMAGE_NAME}:latest" }
            }
        }
    }

    post {
        always {
            sh 'rm -f test-results.xml coverage.xml || true'
            sh "docker rmi ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} || true"
        }
        success {
            echo 'Pipeline succeeded!'
        }
        failure {
            echo 'Pipeline failed.'
        }
    }
}
