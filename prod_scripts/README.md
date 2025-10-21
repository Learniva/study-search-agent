# Production Scripts

This directory contains shell scripts for testing, building, and deploying the Multi-Agent Study & Grading System.

## Available Scripts

### [quick-test.sh](./quick-test.sh)
**Purpose**: Quick development setup test for core services  
**Usage**: `./quick-test.sh`  
**Description**: Tests PostgreSQL and Redis services without building the full application. Ideal for rapid development iteration.

### [test-minimal.sh](./test-minimal.sh)
**Purpose**: Minimal application test with core dependencies  
**Usage**: `./test-minimal.sh`  
**Description**: Builds and tests a minimal version of the application with essential features only. Good for CI/CD pipelines.

### [ultra-test.sh](./ultra-test.sh)
**Purpose**: Ultra-minimal setup test  
**Usage**: `./ultra-test.sh`  
**Description**: Fastest test option with minimal dependencies. Used for quick validation of core functionality.

### [test-container.sh](./test-container.sh)
**Purpose**: Full container testing suite  
**Usage**: `./test-container.sh`  
**Description**: Comprehensive container testing including health checks, API validation, and integration tests.

## Prerequisites

Before running any script:

```bash
# Make scripts executable
chmod +x prod_scripts/*.sh

# Ensure Docker is running
docker --version
docker compose --version
```

## Usage Examples

### Development Testing
```bash
# Quick service validation
./prod_scripts/quick-test.sh

# Minimal app testing
./prod_scripts/test-minimal.sh
```

### Production Validation
```bash
# Full container testing
./prod_scripts/test-container.sh

# Ultra-fast validation
./prod_scripts/ultra-test.sh
```

## Script Execution Order

For comprehensive testing, run scripts in this order:

1. **quick-test.sh** - Validate core services
2. **test-minimal.sh** - Test minimal application
3. **ultra-test.sh** - Fast validation check
4. **test-container.sh** - Full production testing

## Environment Requirements

All scripts require:
- Docker Desktop or Docker Engine
- 4GB+ available RAM
- Network access for image pulls
- Ports 8000-8001 available

## Troubleshooting

### Common Issues

**Port conflicts**:
```bash
# Check port usage
lsof -i :8000
lsof -i :8001
```

**Docker issues**:
```bash
# Clean Docker cache
docker system prune -f

# Reset containers
docker compose down -v
```

**Permission errors**:
```bash
# Fix script permissions
chmod +x prod_scripts/*.sh
```

### Script Output

Each script provides:
- Color-coded status messages
- Health check results
- Error logs when failures occur
- Performance timing information

### Exit Codes

- `0`: Success
- `1`: Build or test failure
- `7`: Network/connectivity issues

## Integration with CI/CD

These scripts are designed for use in automated pipelines:

```yaml
# Example GitHub Actions usage
- name: Run production tests
  run: |
    chmod +x prod_scripts/*.sh
    ./prod_scripts/test-minimal.sh
    ./prod_scripts/ultra-test.sh
```

## Maintenance

Scripts are maintained to:
- Support latest Docker versions
- Provide consistent output formatting
- Handle error conditions gracefully
- Optimize for speed and reliability