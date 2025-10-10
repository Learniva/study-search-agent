"""
Load balancer configuration and session affinity support.

Helps configure nginx, HAProxy, or other load balancers.
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class LoadBalancingAlgorithm(Enum):
    """Load balancing algorithms."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    IP_HASH = "ip_hash"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"


class SessionAffinity(Enum):
    """Session affinity strategies."""
    NONE = "none"
    COOKIE = "cookie"
    IP_HASH = "ip_hash"
    HEADER = "header"


@dataclass
class LoadBalancerConfig:
    """Load balancer configuration."""
    
    algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.LEAST_CONNECTIONS
    session_affinity: SessionAffinity = SessionAffinity.COOKIE
    health_check_path: str = "/health"
    health_check_interval: int = 30
    max_fails: int = 3
    fail_timeout: int = 30
    
    def generate_nginx_config(
        self,
        instances: List[tuple[str, int]],
        upstream_name: str = "study_search_backend"
    ) -> str:
        """
        Generate nginx configuration.
        
        Args:
            instances: List of (host, port) tuples
            upstream_name: Upstream block name
            
        Returns:
            Nginx configuration string
        """
        config_lines = [
            f"upstream {upstream_name} {{",
        ]
        
        # Add load balancing method
        if self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            config_lines.append("    least_conn;")
        elif self.algorithm == LoadBalancingAlgorithm.IP_HASH:
            config_lines.append("    ip_hash;")
        
        # Add servers
        for host, port in instances:
            config_lines.append(
                f"    server {host}:{port} max_fails={self.max_fails} "
                f"fail_timeout={self.fail_timeout}s;"
            )
        
        config_lines.append("}")
        config_lines.append("")
        
        # Server block
        config_lines.extend([
            "server {",
            "    listen 80;",
            "    server_name _;",
            "",
            "    location / {",
            f"        proxy_pass http://{upstream_name};",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "",
        ])
        
        # Session affinity
        if self.session_affinity == SessionAffinity.COOKIE:
            config_lines.extend([
                "        # Session affinity via cookie",
                "        sticky cookie srv_id expires=1h domain=.example.com path=/;",
            ])
        
        config_lines.extend([
            "    }",
            "",
            f"    location {self.health_check_path} {{",
            f"        proxy_pass http://{upstream_name};",
            "        access_log off;",
            "    }",
            "}",
        ])
        
        return "\n".join(config_lines)
    
    def generate_haproxy_config(
        self,
        instances: List[tuple[str, int]],
        backend_name: str = "study_search_backend"
    ) -> str:
        """
        Generate HAProxy configuration.
        
        Args:
            instances: List of (host, port) tuples
            backend_name: Backend block name
            
        Returns:
            HAProxy configuration string
        """
        config_lines = [
            f"backend {backend_name}",
        ]
        
        # Balance algorithm
        if self.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            config_lines.append("    balance roundrobin")
        elif self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            config_lines.append("    balance leastconn")
        elif self.algorithm == LoadBalancingAlgorithm.IP_HASH:
            config_lines.append("    balance source")
        
        # Session affinity
        if self.session_affinity == SessionAffinity.COOKIE:
            config_lines.append("    cookie SERVERID insert indirect nocache")
        
        # Health check
        config_lines.append(
            f"    option httpchk GET {self.health_check_path}"
        )
        
        # Servers
        for i, (host, port) in enumerate(instances):
            server_line = f"    server server{i+1} {host}:{port} check"
            
            if self.session_affinity == SessionAffinity.COOKIE:
                server_line += f" cookie server{i+1}"
            
            config_lines.append(server_line)
        
        return "\n".join(config_lines)
    
    def generate_docker_compose(
        self,
        app_image: str,
        replicas: int = 3,
        port: int = 8000
    ) -> str:
        """
        Generate docker-compose configuration for scaling.
        
        Args:
            app_image: Docker image name
            replicas: Number of replicas
            port: Application port
            
        Returns:
            Docker Compose YAML string
        """
        return f"""version: '3.8'

services:
  app:
    image: {app_image}
    deploy:
      replicas: {replicas}
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}{self.health_check_path}"]
      interval: {self.health_check_interval}s
      timeout: 10s
      retries: {self.max_fails}
  
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
  
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=grading_system
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - app

volumes:
  redis_data:
  postgres_data:
"""
    
    def generate_kubernetes_deployment(
        self,
        app_name: str,
        app_image: str,
        replicas: int = 3,
        port: int = 8000
    ) -> str:
        """
        Generate Kubernetes deployment configuration.
        
        Args:
            app_name: Application name
            app_image: Docker image name
            replicas: Number of replicas
            port: Application port
            
        Returns:
            Kubernetes YAML string
        """
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app_name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {app_name}
  template:
    metadata:
      labels:
        app: {app_name}
    spec:
      containers:
      - name: {app_name}
        image: {app_image}
        ports:
        - containerPort: {port}
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        livenessProbe:
          httpGet:
            path: {self.health_check_path}
            port: {port}
          initialDelaySeconds: 30
          periodSeconds: {self.health_check_interval}
        readinessProbe:
          httpGet:
            path: {self.health_check_path}
            port: {port}
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: {app_name}-service
spec:
  type: LoadBalancer
  selector:
    app: {app_name}
  ports:
  - protocol: TCP
    port: 80
    targetPort: {port}
  sessionAffinity: {"ClientIP" if self.session_affinity == SessionAffinity.IP_HASH else "None"}
"""

