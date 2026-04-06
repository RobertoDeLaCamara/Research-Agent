// Webhook: notifyCommit via Gitea webhook #4
pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '5'))
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
    }

    environment {
        REGISTRY = "192.168.1.48:5000"
        IMAGE_NAME = "research-agent"
        NO_PROXY = 'localhost,127.0.0.1,192.168.1.0/24,192.168.1.48,192.168.1.62,192.168.1.45'
        no_proxy = 'localhost,127.0.0.1,192.168.1.0/24,192.168.1.48,192.168.1.62,192.168.1.45'
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
                                --cov-report=xml:coverage.xml \
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
                }
            }
        }

        stage('Push to Registry') {
            steps {
                echo "Pushing image to ${REGISTRY}..."
                sh "docker push ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}"
                sh "docker push ${REGISTRY}/${IMAGE_NAME}:latest"
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
