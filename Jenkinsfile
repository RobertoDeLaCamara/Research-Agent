pipeline {
    agent any

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

        stage('Test') {
            steps {
                echo 'Running tests inside container...'
                sh "docker run --rm -e TAVILY_API_KEY=test-key ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} python -m pytest tests/ -v --ignore=tests/test_rag_tools.py"
            }
        }

        stage('Push to Registry') {
            steps {
                echo "Pushing image to ${REGISTRY}..."
                sh "docker push ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}"
                sh "docker push ${REGISTRY}/${IMAGE_NAME}:latest"
            }
        }

        stage('Registry Verify') {
            steps {
                echo 'Verifying image in local registry...'
                sh "curl -s http://${REGISTRY}/v2/${IMAGE_NAME}/tags/list"
            }
        }
    }

    post {
        success {
            echo "Build #${BUILD_NUMBER} pushed to ${REGISTRY}/${IMAGE_NAME}"
        }
        failure {
            echo "Build #${BUILD_NUMBER} failed."
        }
        always {
            sh "docker rmi ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} || true"
        }
    }
}
