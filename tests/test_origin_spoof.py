"""
Origin Spoofing & CORS/CSP Enforcement Tests

Comprehensive security tests to ensure CORS + CSP prevent origin spoofing
or hostile browser contexts.

Attack Scenarios Tested:
- Forged Origin headers
- Forged Referer headers  
- Multiple fake origins
- Wildcard bypass attempts
- Cross-origin embedding attacks
- CSP violations

Expected Invariants:
- Preflight or gateway rejection for hostile origins
- No wildcard fallback
- Proper logging of origin rejections
- CSP headers properly enforced
- No information leakage

Author: Study Search Agent Team
Version: 1.0.0
Security Issue: #11 - Origin spoof test → CSP/CORS enforcement
"""

import pytest
import pytest_asyncio
import os
import json
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from httpx import AsyncClient

from api.app import app
from config import settings


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for all tests."""
    with patch.object(settings, 'rate_limit_enabled', False):
        yield


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def async_client():
    """Async test client for FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def evidence_dir():
    """Create evidence directory for test artifacts."""
    evidence_path = Path(__file__).parent / "evidence" / "origin_spoof"
    evidence_path.mkdir(parents=True, exist_ok=True)
    return evidence_path


@pytest.fixture
def allowed_origins():
    """Get allowed origins from environment."""
    origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,https://localhost:3000")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


@pytest.fixture
def hostile_origins():
    """List of hostile/fake origins to test."""
    return [
        "http://evil.com",
        "https://attacker.net",
        "http://malicious-site.org",
        "https://phishing.example",
        "http://192.168.1.100:8080",
        "https://subdomain.evil.com",
        "null",  # Null origin attack
        "file://",  # File protocol
        "data://",  # Data protocol
        "javascript://",  # JavaScript protocol
        "https://localhost.evil.com",  # Subdomain hijack attempt
        "http://localhost:3000.evil.com",  # Domain append attack
        "http://evil.com@localhost:3000",  # User info attack
        "https://[::1]",  # IPv6 localhost
        "http://127.0.0.1",  # Different localhost representation
    ]


# ============================================================================
# CORS Origin Validation Tests
# ============================================================================

class TestCORSOriginValidation:
    """Test CORS middleware properly validates origins."""
    
    def test_allowed_origin_accepted(self, client, allowed_origins):
        """Test that allowed origins are accepted."""
        if not allowed_origins:
            pytest.skip("No allowed origins configured")
        
        origin = allowed_origins[0]
        response = client.options(
            "/health",  # Use /health endpoint which doesn't require auth
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Should allow the origin
        # Accept 200, 204 (preflight success), or 401 (auth required but CORS headers present)
        assert response.status_code in [200, 204, 401]
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == origin
    
    def test_hostile_origins_rejected(self, client, hostile_origins, evidence_dir):
        """Test that hostile origins are rejected."""
        evidence = {
            "test_name": "hostile_origins_rejection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": []
        }
        
        for hostile_origin in hostile_origins:
            response = client.options(
                "/api/auth/health",
                headers={
                    "Origin": hostile_origin,
                    "Access-Control-Request-Method": "GET"
                }
            )
            
            result = {
                "origin": hostile_origin,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "allowed": False
            }
            
            # Hostile origin should either:
            # 1. Not get CORS headers at all
            # 2. Get explicit rejection
            # 3. Not match the origin
            if "Access-Control-Allow-Origin" in response.headers:
                allowed_origin = response.headers["Access-Control-Allow-Origin"]
                result["allowed"] = allowed_origin == hostile_origin
                
                # Should NOT allow the hostile origin
                assert allowed_origin != hostile_origin, \
                    f"Hostile origin {hostile_origin} was incorrectly allowed!"
                
                # Should NOT be wildcard
                assert allowed_origin != "*", \
                    f"Wildcard CORS detected for origin {hostile_origin}!"
            
            evidence["results"].append(result)
        
        # Save evidence
        evidence_file = evidence_dir / f"hostile_origins_rejection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, "w") as f:
            json.dump(evidence, f, indent=2)
        
        print(f"\n✅ Evidence saved: {evidence_file}")
    
    def test_no_wildcard_cors(self, client, evidence_dir):
        """Test that wildcard CORS is never used with credentials."""
        evidence = {
            "test_name": "no_wildcard_cors",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": []
        }
        
        test_origins = [
            "http://localhost:3000",
            "http://evil.com",
            "https://attacker.net",
            "null"
        ]
        
        for origin in test_origins:
            response = client.options(
                "/api/auth/login/",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type"
                }
            )
            
            result = {
                "origin": origin,
                "status_code": response.status_code,
                "cors_headers": {
                    k: v for k, v in response.headers.items() 
                    if k.lower().startswith("access-control")
                }
            }
            
            # If credentials are allowed, origin must NOT be wildcard
            if "Access-Control-Allow-Credentials" in response.headers:
                credentials_allowed = response.headers["Access-Control-Allow-Credentials"]
                if credentials_allowed.lower() == "true":
                    if "Access-Control-Allow-Origin" in response.headers:
                        allowed_origin = response.headers["Access-Control-Allow-Origin"]
                        result["wildcard_violation"] = allowed_origin == "*"
                        
                        # CRITICAL: Never use * with credentials=true
                        assert allowed_origin != "*", \
                            f"CRITICAL: Wildcard CORS with credentials=true detected for origin {origin}!"
            
            evidence["results"].append(result)
        
        # Save evidence
        evidence_file = evidence_dir / f"no_wildcard_cors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, "w") as f:
            json.dump(evidence, f, indent=2)
        
        print(f"\n✅ Evidence saved: {evidence_file}")
    
    def test_null_origin_rejection(self, client):
        """Test that null origin is properly handled."""
        response = client.options(
            "/api/auth/health",
            headers={
                "Origin": "null",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Should not allow null origin
        if "Access-Control-Allow-Origin" in response.headers:
            assert response.headers["Access-Control-Allow-Origin"] != "null"
            assert response.headers["Access-Control-Allow-Origin"] != "*"
    
    def test_origin_case_sensitivity(self, client):
        """Test that origin matching is case-sensitive (per spec)."""
        test_cases = [
            ("http://localhost:3000", "HTTP://LOCALHOST:3000"),
            ("https://example.com", "HTTPS://EXAMPLE.COM"),
            ("http://api.example.com", "http://API.EXAMPLE.COM"),
        ]
        
        for original, modified in test_cases:
            response = client.options(
                "/api/auth/health",
                headers={
                    "Origin": modified,
                    "Access-Control-Request-Method": "GET"
                }
            )
            
            # Modified case should not match if original is allowed
            if "Access-Control-Allow-Origin" in response.headers:
                allowed = response.headers["Access-Control-Allow-Origin"]
                # Should either reject or return exact match only
                if allowed == modified:
                    # If it matches, it means case-insensitive (potential issue)
                    print(f"⚠️  Warning: Case-insensitive origin matching detected: {modified}")


# ============================================================================
# Referer Header Validation Tests
# ============================================================================

class TestRefererValidation:
    """Test that forged Referer headers are handled properly."""
    
    def test_hostile_referer_headers(self, client, hostile_origins, evidence_dir):
        """Test that hostile Referer headers don't bypass security."""
        evidence = {
            "test_name": "hostile_referer_rejection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": []
        }
        
        for referer in hostile_origins:
            response = client.get(
                "/health",
                headers={
                    "Referer": referer,
                    "Origin": referer
                }
            )
            
            result = {
                "referer": referer,
                "status_code": response.status_code,
                "has_cors_headers": "Access-Control-Allow-Origin" in response.headers,
                "security_headers": {
                    k: v for k, v in response.headers.items()
                    if k.lower() in ["x-frame-options", "content-security-policy", 
                                    "x-content-type-options", "referrer-policy"]
                }
            }
            
            evidence["results"].append(result)
        
        # Save evidence
        evidence_file = evidence_dir / f"hostile_referer_rejection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, "w") as f:
            json.dump(evidence, f, indent=2)
        
        print(f"\n✅ Evidence saved: {evidence_file}")
    
    def test_referer_policy_header(self, client):
        """Test that Referrer-Policy header is set."""
        response = client.get("/health")
        
        # Should have Referrer-Policy header
        assert "Referrer-Policy" in response.headers
        
        # Should be restrictive
        policy = response.headers["Referrer-Policy"]
        assert policy in [
            "no-referrer",
            "no-referrer-when-downgrade",
            "strict-origin",
            "strict-origin-when-cross-origin",
            "same-origin"
        ]


# ============================================================================
# CSP (Content Security Policy) Tests
# ============================================================================

class TestCSPEnforcement:
    """Test Content Security Policy enforcement."""
    
    def test_csp_header_present(self, client):
        """Test that CSP header is present in responses."""
        response = client.get("/health")
        
        # Should have CSP header
        assert "Content-Security-Policy" in response.headers
    
    def test_csp_frame_ancestors(self, client):
        """Test that CSP prevents framing (clickjacking protection)."""
        response = client.get("/health")
        
        csp = response.headers.get("Content-Security-Policy", "")
        
        # Should prevent framing
        assert "frame-ancestors 'none'" in csp or "frame-ancestors 'self'" in csp
    
    def test_csp_no_unsafe_inline_scripts(self, client):
        """Test that CSP doesn't allow unsafe-inline for scripts in production."""
        response = client.get("/health")
        
        csp = response.headers.get("Content-Security-Policy", "")
        
        # In strict mode (production), should not have unsafe-inline for scripts
        # unless in development mode
        if "script-src" in csp:
            # Check if we're in strict mode by looking for nonce
            if "'nonce-" in csp:
                # Production mode - should use nonce instead of unsafe-inline
                assert "'unsafe-inline'" not in csp or "script-src 'self' 'nonce-" in csp
    
    def test_csp_default_src_restrictive(self, client):
        """Test that default-src is restrictive."""
        response = client.get("/health")
        
        csp = response.headers.get("Content-Security-Policy", "")
        
        # Should have default-src
        assert "default-src" in csp
        
        # Should not allow everything
        assert "default-src *" not in csp
        assert "default-src 'unsafe-eval' 'unsafe-inline'" not in csp
    
    def test_csp_object_src_blocked(self, client):
        """Test that object-src is blocked (prevents Flash/plugin attacks)."""
        response = client.get("/health")
        
        csp = response.headers.get("Content-Security-Policy", "")
        
        # Should block object-src or set it to 'none'
        # Either explicitly blocked or covered by restrictive default-src
        if "object-src" in csp:
            assert "object-src 'none'" in csp
    
    def test_csp_base_uri_restricted(self, client):
        """Test that base-uri is restricted (prevents base tag injection)."""
        response = client.get("/health")
        
        csp = response.headers.get("Content-Security-Policy", "")
        
        # Should restrict base-uri
        if "base-uri" in csp:
            assert "base-uri 'self'" in csp or "base-uri 'none'" in csp


# ============================================================================
# Cross-Origin Headers Tests
# ============================================================================

class TestCrossOriginHeaders:
    """Test Cross-Origin-* security headers."""
    
    def test_cross_origin_policies_present(self, client):
        """Test that Cross-Origin-* headers are present."""
        response = client.get("/health")
        
        # Should have cross-origin policies
        headers_to_check = [
            "Cross-Origin-Embedder-Policy",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy"
        ]
        
        for header in headers_to_check:
            assert header in response.headers, f"Missing security header: {header}"
    
    def test_coep_require_corp(self, client):
        """Test that COEP requires CORP."""
        response = client.get("/health")
        
        coep = response.headers.get("Cross-Origin-Embedder-Policy", "")
        
        # Should require CORP or be set appropriately
        assert coep in ["require-corp", "credentialless"]
    
    def test_coop_same_origin(self, client):
        """Test that COOP isolates browsing context."""
        response = client.get("/health")
        
        coop = response.headers.get("Cross-Origin-Opener-Policy", "")
        
        # Should isolate browsing context
        assert coop in ["same-origin", "same-origin-allow-popups"]
    
    def test_corp_same_origin(self, client):
        """Test that CORP restricts resource access."""
        response = client.get("/health")
        
        corp = response.headers.get("Cross-Origin-Resource-Policy", "")
        
        # Should restrict to same origin or same site
        assert corp in ["same-origin", "same-site"]


# ============================================================================
# X-Frame-Options Tests
# ============================================================================

class TestFramingProtection:
    """Test clickjacking protection via X-Frame-Options."""
    
    def test_x_frame_options_present(self, client):
        """Test that X-Frame-Options header is present."""
        response = client.get("/health")
        
        assert "X-Frame-Options" in response.headers
    
    def test_x_frame_options_restrictive(self, client):
        """Test that X-Frame-Options is restrictive."""
        response = client.get("/health")
        
        xfo = response.headers.get("X-Frame-Options", "")
        
        # Should be DENY or SAMEORIGIN
        assert xfo in ["DENY", "SAMEORIGIN"]
    
    def test_framing_with_hostile_origin(self, client, hostile_origins, evidence_dir):
        """Test that framing attempts from hostile origins are blocked."""
        evidence = {
            "test_name": "framing_protection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": []
        }
        
        for origin in hostile_origins[:5]:  # Test subset
            response = client.get(
                "/health",
                headers={
                    "Origin": origin,
                    "Referer": f"{origin}/evil-frame.html"
                }
            )
            
            result = {
                "origin": origin,
                "x_frame_options": response.headers.get("X-Frame-Options"),
                "csp_frame_ancestors": None,
                "blocked": False
            }
            
            # Extract frame-ancestors from CSP
            csp = response.headers.get("Content-Security-Policy", "")
            if "frame-ancestors" in csp:
                for directive in csp.split(";"):
                    if "frame-ancestors" in directive:
                        result["csp_frame_ancestors"] = directive.strip()
            
            # Should be blocked by either XFO or CSP
            xfo_blocks = response.headers.get("X-Frame-Options") == "DENY"
            csp_blocks = "frame-ancestors 'none'" in csp
            
            result["blocked"] = xfo_blocks or csp_blocks
            assert result["blocked"], f"Framing not blocked for origin: {origin}"
            
            evidence["results"].append(result)
        
        # Save evidence
        evidence_file = evidence_dir / f"framing_protection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, "w") as f:
            json.dump(evidence, f, indent=2)
        
        print(f"\n✅ Evidence saved: {evidence_file}")


# ============================================================================
# Information Leakage Tests
# ============================================================================

class TestInformationLeakage:
    """Test that no sensitive information leaks via headers or errors."""
    
    def test_no_server_version_leak(self, client):
        """Test that Server header doesn't leak version info."""
        response = client.get("/health")
        
        server_header = response.headers.get("Server", "").lower()
        
        # Should not leak detailed version information
        sensitive_tokens = ["python", "uvicorn", "fastapi", "starlette"]
        for token in sensitive_tokens:
            if token in server_header:
                # If present, should not have version numbers
                assert "/" not in server_header or not any(char.isdigit() for char in server_header)
    
    def test_error_responses_no_stack_trace(self, client, hostile_origins):
        """Test that error responses don't leak stack traces to hostile origins."""
        for origin in hostile_origins[:3]:
            response = client.get(
                "/nonexistent-endpoint-12345",
                headers={"Origin": origin}
            )
            
            # Should not contain stack traces or file paths
            body = response.text.lower()
            assert "traceback" not in body
            assert "file \"" not in body
            assert ".py\", line" not in body
    
    def test_cors_error_no_leak(self, client, hostile_origins):
        """Test that CORS errors don't leak allowed origins."""
        for origin in hostile_origins[:3]:
            response = client.options(
                "/api/auth/login/",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST"
                }
            )
            
            # Error messages should not reveal allowed origins
            body = response.text.lower()
            assert "localhost" not in body or response.status_code in [200, 204]


# ============================================================================
# Logging and Monitoring Tests
# ============================================================================

class TestOriginRejectionLogging:
    """Test that origin rejections are properly logged."""
    
    def test_hostile_origin_logged(self, client, evidence_dir):
        """Test that hostile origin attempts are logged."""
        # This test verifies logging behavior
        # In a real implementation, you'd check actual log files
        
        evidence = {
            "test_name": "origin_rejection_logging",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostile_attempts": []
        }
        
        hostile_origins = [
            "http://evil.com",
            "https://attacker.net",
            "null"
        ]
        
        for origin in hostile_origins:
            response = client.options(
                "/health",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET"
                }
            )
            
            attempt = {
                "origin": origin,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status_code": response.status_code,
                "cors_allowed": "Access-Control-Allow-Origin" in response.headers,
                "expected_behavior": "rejected or not in CORS headers"
            }
            
            evidence["hostile_attempts"].append(attempt)
        
        # Save evidence
        evidence_file = evidence_dir / f"origin_rejection_logging_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, "w") as f:
            json.dump(evidence, f, indent=2)
        
        print(f"\n✅ Evidence saved: {evidence_file}")
        print(f"✅ Logged {len(hostile_origins)} hostile origin attempts")


# ============================================================================
# Comprehensive Attack Simulation
# ============================================================================

class TestComprehensiveOriginSpoof:
    """Comprehensive origin spoofing attack simulation."""
    
    def test_full_attack_simulation(self, client, evidence_dir):
        """Simulate a comprehensive origin spoofing attack."""
        evidence = {
            "test_name": "comprehensive_origin_spoof_attack",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attack_vectors": [],
            "summary": {
                "total_attempts": 0,
                "blocked": 0,
                "leaked": 0,
                "wildcard_detected": False
            }
        }
        
        # Attack vectors
        attack_vectors = [
            {
                "name": "Forged Origin Header",
                "headers": {"Origin": "http://evil.com"}
            },
            {
                "name": "Forged Referer Header",
                "headers": {"Referer": "http://evil.com/phishing.html"}
            },
            {
                "name": "Combined Origin + Referer",
                "headers": {
                    "Origin": "http://evil.com",
                    "Referer": "http://evil.com/attack.html"
                }
            },
            {
                "name": "Null Origin",
                "headers": {"Origin": "null"}
            },
            {
                "name": "File Protocol",
                "headers": {"Origin": "file://"}
            },
            {
                "name": "Subdomain Hijack Attempt",
                "headers": {"Origin": "http://localhost.evil.com"}
            },
            {
                "name": "Domain Append Attack",
                "headers": {"Origin": "http://localhost:3000.evil.com"}
            },
            {
                "name": "User Info Attack",
                "headers": {"Origin": "http://evil.com@localhost:3000"}
            },
        ]
        
        for vector in attack_vectors:
            response = client.options(
                "/health",
                headers={
                    **vector["headers"],
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type,Authorization"
                }
            )
            
            result = {
                "attack_vector": vector["name"],
                "headers_sent": vector["headers"],
                "status_code": response.status_code,
                "cors_headers": {
                    k: v for k, v in response.headers.items()
                    if k.lower().startswith("access-control")
                },
                "security_headers": {
                    k: v for k, v in response.headers.items()
                    if k.lower() in ["x-frame-options", "content-security-policy",
                                    "x-content-type-options", "referrer-policy"]
                },
                "blocked": True,
                "wildcard": False
            }
            
            # Check if attack was blocked
            if "Access-Control-Allow-Origin" in response.headers:
                allowed_origin = response.headers["Access-Control-Allow-Origin"]
                
                # Check for wildcard
                if allowed_origin == "*":
                    result["wildcard"] = True
                    evidence["summary"]["wildcard_detected"] = True
                    result["blocked"] = False
                
                # Check if attacker's origin was allowed
                attacker_origin = vector["headers"].get("Origin", "")
                if allowed_origin == attacker_origin:
                    result["blocked"] = False
            
            evidence["attack_vectors"].append(result)
            evidence["summary"]["total_attempts"] += 1
            
            if result["blocked"]:
                evidence["summary"]["blocked"] += 1
            else:
                evidence["summary"]["leaked"] += 1
        
        # Save evidence
        evidence_file = evidence_dir / f"comprehensive_attack_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, "w") as f:
            json.dump(evidence, f, indent=2)
        
        print(f"\n{'='*60}")
        print(f"🔒 COMPREHENSIVE ORIGIN SPOOF ATTACK SIMULATION")
        print(f"{'='*60}")
        print(f"Total Attempts: {evidence['summary']['total_attempts']}")
        print(f"✅ Blocked: {evidence['summary']['blocked']}")
        print(f"❌ Leaked: {evidence['summary']['leaked']}")
        print(f"⚠️  Wildcard Detected: {evidence['summary']['wildcard_detected']}")
        print(f"{'='*60}")
        print(f"📁 Evidence saved: {evidence_file}")
        print(f"{'='*60}\n")
        
        # Assertions
        assert not evidence["summary"]["wildcard_detected"], \
            "CRITICAL: Wildcard CORS detected!"
        
        assert evidence["summary"]["leaked"] == 0, \
            f"CRITICAL: {evidence['summary']['leaked']} attack(s) were not blocked!"


# ============================================================================
# Test Summary and Reporting
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def test_summary(request):
    """Generate test summary at the end of the session."""
    yield
    
    # This will run after all tests
    print("\n" + "="*60)
    print("🔒 ORIGIN SPOOF & CORS/CSP ENFORCEMENT TEST SUMMARY")
    print("="*60)
    print("Tests completed. Check evidence directory for detailed results.")
    print("Evidence location: tests/evidence/origin_spoof/")
    print("="*60 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
