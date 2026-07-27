#!/bin/bash

# AWS ECR Build and Push Script with Semantic Versioning
# This script builds a Docker image, tags it with semantic versioning, and pushes to AWS ECR

set -e  # Exit on any error

# Configuration
AWS_REGION="ap-south-1"
AWS_ACCOUNT_ID="352196745834"
REPOSITORY_NAME="thinko/core-service"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_REPOSITORY="${ECR_REGISTRY}/${REPOSITORY_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command_exists aws; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    if ! command_exists git; then
        print_error "Git is not installed. Please install it first."
        exit 1
    fi
    
    if ! command_exists node; then
        print_error "Node.js is not installed. Please install it first."
        exit 1
    fi
    
    print_success "All prerequisites are met"
}

# Function to generate semantic version
generate_version() {
    print_status "Generating semantic version..."
    
    # Check if package.json exists
    if [ ! -f "package.json" ]; then
        print_error "package.json not found. Please run this script from the project root."
        exit 1
    fi
    
    # Get current version from package.json
    CURRENT_VERSION=$(node -p "require('./package.json').version")
    
    if [ -z "$CURRENT_VERSION" ]; then
        print_error "Could not read version from package.json"
        exit 1
    fi
    
    print_status "Current version in package.json: $CURRENT_VERSION"
    
    # Split version into parts
    MAJOR=$(echo $CURRENT_VERSION | cut -d. -f1)
    MINOR=$(echo $CURRENT_VERSION | cut -d. -f2)
    PATCH=$(echo $CURRENT_VERSION | cut -d. -f3)
    
    # Increment version based on type
    case $VERSION_TYPE in
        "major")
            NEW_MAJOR=$((MAJOR + 1))
            NEW_MINOR=0
            NEW_PATCH=0
            ;;
        "minor")
            NEW_MAJOR=$MAJOR
            NEW_MINOR=$((MINOR + 1))
            NEW_PATCH=0
            ;;
        "patch"|*)
            NEW_MAJOR=$MAJOR
            NEW_MINOR=$MINOR
            NEW_PATCH=$((PATCH + 1))
            ;;
    esac
    
    NEW_VERSION_NUMBER="${NEW_MAJOR}.${NEW_MINOR}.${NEW_PATCH}"
    NEW_VERSION="v${NEW_VERSION_NUMBER}"
    DOCKER_VERSION=$NEW_VERSION_NUMBER
    
    print_status "Incrementing $VERSION_TYPE version: $CURRENT_VERSION → $NEW_VERSION_NUMBER"
    
    # Update package.json with new version
    print_status "Updating package.json with new version..."
    
    # Use node to update package.json
    node -e "
        const fs = require('fs');
        const pkg = require('./package.json');
        pkg.version = '$NEW_VERSION_NUMBER';
        fs.writeFileSync('./package.json', JSON.stringify(pkg, null, 2) + '\n');
    "
    
    if [ $? -eq 0 ]; then
        print_success "Updated package.json version to $NEW_VERSION_NUMBER"
    else
        print_error "Failed to update package.json"
        exit 1
    fi
    
    print_success "Generated version: $NEW_VERSION (Docker tag: $DOCKER_VERSION)"
}

# Function to authenticate with ECR
authenticate_ecr() {
    print_status "Authenticating with AWS ECR..."
    
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
    
    if [ $? -eq 0 ]; then
        print_success "Successfully authenticated with ECR"
    else
        print_error "Failed to authenticate with ECR"
        exit 1
    fi
}

# Function to build Docker image
build_image() {
    print_status "Building Docker image for AMD64 architecture..."
    
    # Check if buildx is available
    if ! docker buildx version >/dev/null 2>&1; then
        print_warning "Docker buildx not available, using regular build (may cause architecture issues)"
        # Build the image with both version tag and latest tag (single architecture)
        docker build -t $REPOSITORY_NAME:$DOCKER_VERSION -t $REPOSITORY_NAME:latest .
    else
        print_status "Using Docker buildx for multi-platform build..."
        
        # Create a new builder instance if it doesn't exist
        docker buildx create --name multiarch-builder --use --bootstrap 2>/dev/null || true
        
        # Build for AMD64 architecture (Linux x86_64) - what ECS EC2 instances typically use
        docker buildx build \
            --platform linux/amd64 \
            --tag $REPOSITORY_NAME:$DOCKER_VERSION \
            --tag $REPOSITORY_NAME:latest \
            --load \
            .
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Successfully built Docker image"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

# Function to tag images for ECR
tag_images() {
    print_status "Tagging images for ECR..."
    
    # Tag for versioned push
    docker tag $REPOSITORY_NAME:$DOCKER_VERSION $ECR_REPOSITORY:$DOCKER_VERSION
    
    # Tag for latest push
    docker tag $REPOSITORY_NAME:latest $ECR_REPOSITORY:latest
    
    print_success "Images tagged successfully"
}

# Function to push images to ECR
push_images() {
    print_status "Pushing images to ECR..."
    
    # Push versioned image
    print_status "Pushing version $DOCKER_VERSION..."
    docker push $ECR_REPOSITORY:$DOCKER_VERSION
    
    # Push latest image
    print_status "Pushing latest..."
    docker push $ECR_REPOSITORY:latest
    
    if [ $? -eq 0 ]; then
        print_success "Successfully pushed images to ECR"
    else
        print_error "Failed to push images to ECR"
        exit 1
    fi
}

# Function to create and push git tag
create_git_tag() {
    # Check if we're on main/master branch for tagging
    CURRENT_BRANCH=$(git branch --show-current)
    
    if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
        print_warning "Not on main/master branch (current: $CURRENT_BRANCH). Skipping git tag creation."
        print_warning "Consider creating the tag manually after merging to main: git tag -a $NEW_VERSION -m 'Release $NEW_VERSION'"
        return
    fi
    
    # Check if working directory is clean
    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
        print_warning "Working directory has uncommitted changes. Committing package.json update..."
        git add package.json
        git commit -m "Bump version to $NEW_VERSION_NUMBER"
    fi
    
    # Check if tag already exists
    if git tag | grep -q "^$NEW_VERSION$"; then
        print_warning "Tag $NEW_VERSION already exists. Skipping tag creation."
        return
    fi
    
    print_status "Creating git tag $NEW_VERSION..."
    
    # Create annotated tag
    git tag -a $NEW_VERSION -m "Release $NEW_VERSION - Docker image pushed to ECR"
    
    if [ $? -eq 0 ]; then
        print_success "Git tag $NEW_VERSION created locally"
        print_warning "Run 'git push origin $NEW_VERSION' to push the tag to remote repository"
        print_warning "Also run 'git push origin $CURRENT_BRANCH' to push the version bump commit"
    else
        print_error "Failed to create git tag"
    fi
}

# Function to cleanup local images (optional)
cleanup_images() {
    if [ "$CLEANUP_LOCAL" = "true" ]; then
        print_status "Cleaning up local Docker images..."
        docker rmi $REPOSITORY_NAME:$DOCKER_VERSION $REPOSITORY_NAME:latest 2>/dev/null || true
        docker rmi $ECR_REPOSITORY:$DOCKER_VERSION $ECR_REPOSITORY:latest 2>/dev/null || true
        print_success "Local images cleaned up"
    fi
}

# Function to display final summary
display_summary() {
    echo ""
    echo "================================="
    echo "🚀 BUILD AND PUSH COMPLETED! 🚀"
    echo "================================="
    echo "Version: $NEW_VERSION"
    echo "Docker Version: $DOCKER_VERSION"
    echo "ECR Repository: $ECR_REPOSITORY"
    echo "Images pushed:"
    echo "  - $ECR_REPOSITORY:$DOCKER_VERSION"
    echo "  - $ECR_REPOSITORY:latest"
    echo ""
    echo "To deploy this version, use:"
    echo "  docker pull $ECR_REPOSITORY:$DOCKER_VERSION"
    echo ""
}

# Main execution
main() {
    echo "🐳 AWS ECR Build and Push Script"
    echo "================================="
    echo ""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cleanup)
                CLEANUP_LOCAL="true"
                shift
                ;;
            --major)
                VERSION_TYPE="major"
                shift
                ;;
            --minor)
                VERSION_TYPE="minor"
                shift
                ;;
            --patch)
                VERSION_TYPE="patch"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --cleanup     Remove local Docker images after push"
                echo "  --major       Increment major version (X.0.0)"
                echo "  --minor       Increment minor version (x.X.0)"
                echo "  --patch       Increment patch version (x.x.X) [default]"
                echo "  --help, -h    Show this help message"
                echo ""
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Set default version type if not specified
    VERSION_TYPE=${VERSION_TYPE:-"patch"}
    
    # Execute steps
    check_prerequisites
    generate_version
    authenticate_ecr
    build_image
    tag_images
    push_images
    create_git_tag
    cleanup_images
    display_summary
    
    print_success "All operations completed successfully! 🎉"
}

# Run main function with all arguments
main "$@"
