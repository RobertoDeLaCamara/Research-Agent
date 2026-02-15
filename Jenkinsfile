pipeline {
    agent {
        label 'built-in'
    }

    environment {
        REGISTRY = "192.168.1.86:5000"
        IMAGE_NAME = "research-agent"
        NO_PROXY = 'localhost,127.0.0.1,192.168.1.0/24,192.168.1.86,192.168.1.62'
        no_proxy = 'localhost,127.0.0.1,192.168.1.0/24,192.168.1.86,192.168.1.62'
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
                sh """
                docker run --rm \
                    -e TAVILY_API_KEY=test-key \
                    ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} \
                    python -m pytest tests/ -v --cov=src --cov-report=xml:coverage.xml
                """
            }
        }

        stage('Integration Tests') {
            steps {
                echo 'Running integration tests (Health Check)...'
                script {
                    // Start the container in detached mode
                    try {
                        sh "docker run -d --name integration-test-${BUILD_NUMBER} ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}"
                        
                        // Wait for the service to start
                        sleep 10
                        
                        // Check health using the internal healthcheck defined in Dockerfile
                        sh "docker exec integration-test-${BUILD_NUMBER} curl -f http://localhost:8501/_stcore/health"
                    } finally {
                        // Cleanup
                        sh "docker stop integration-test-${BUILD_NUMBER} || true"
                        sh "docker rm integration-test-${BUILD_NUMBER} || true"
                    }
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
            // Clean up old images to save space
            sh "docker rmi ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} || true"
        }
        failure {
            echo "Pipeline failed."
        }
        success {
            echo "Pipeline succeeded!"
        }
    }
}
