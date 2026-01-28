#!/usr/bin/env python
"""Verify OpenAPI documentation generation."""

import json
from agent_os.server.app import app

def verify_openapi():
    """Verify OpenAPI schema is properly generated."""
    # Get OpenAPI schema
    openapi_schema = app.openapi()

    # Print basic info
    print("=" * 60)
    print("OpenAPI Documentation Verification")
    print("=" * 60)
    print(f"\nTitle: {openapi_schema['info']['title']}")
    print(f"Version: {openapi_schema['info']['version']}")
    print(f"Description: {openapi_schema['info'].get('description', 'N/A')}")

    # Count endpoints by category
    print("\n" + "=" * 60)
    print("API Endpoints Summary")
    print("=" * 60)

    endpoints_by_tag = {}
    for path, methods in openapi_schema['paths'].items():
        for method, details in methods.items():
            tags = details.get('tags', ['untagged'])
            tag = tags[0] if tags else 'untagged'
            if tag not in endpoints_by_tag:
                endpoints_by_tag[tag] = []
            endpoint_str = f"{method.upper():6} {path}"
            endpoints_by_tag[tag].append(endpoint_str)

    # Print endpoints grouped by tag
    for tag, endpoints in sorted(endpoints_by_tag.items()):
        print(f"\n[{tag}] ({len(endpoints)} endpoints)")
        for endpoint in sorted(endpoints):
            print(f"  {endpoint}")

    # Verify authentication endpoints
    print("\n" + "=" * 60)
    print("Authentication Endpoints Verification")
    print("=" * 60)

    auth_endpoints = [
        "POST /api/v1/auth/register",
        "POST /api/v1/auth/login",
        "GET /api/v1/auth/me",
        "PUT /api/v1/auth/settings",
    ]

    for endpoint in auth_endpoints:
        method, path = endpoint.split()
        method_lower = method.lower()
        if path in openapi_schema['paths'] and method_lower in openapi_schema['paths'][path]:
            details = openapi_schema['paths'][path][method_lower]
            print(f"[OK] {endpoint}")
            print(f"  Summary: {details.get('summary', 'N/A')}")
            print(f"  Tags: {details.get('tags', [])}")
        else:
            print(f"[FAIL] {endpoint} - NOT FOUND")

    # Verify knowledge endpoints
    print("\n" + "=" * 60)
    print("Knowledge Endpoints Verification")
    print("=" * 60)

    knowledge_endpoints = [
        ("POST", "/api/v1/knowledge/inbox"),
        ("GET", "/api/v1/knowledge/inbox"),
        ("GET", "/api/v1/knowledge/inbox/{id}"),
        ("PUT", "/api/v1/knowledge/inbox/{id}"),
        ("DELETE", "/api/v1/knowledge/inbox/{id}"),
        ("POST", "/api/v1/knowledge/cards"),
        ("GET", "/api/v1/knowledge/cards"),
        ("GET", "/api/v1/knowledge/cards/{id}"),
        ("PUT", "/api/v1/knowledge/cards/{id}"),
        ("DELETE", "/api/v1/knowledge/cards/{id}"),
        ("POST", "/api/v1/knowledge/cards/search"),
        ("GET", "/api/v1/knowledge/cards/{id}/similar"),
    ]

    for method, path in knowledge_endpoints:
        if path in openapi_schema['paths'] and method.lower() in openapi_schema['paths'][path]:
            details = openapi_schema['paths'][path][method.lower()]
            print(f"[OK] {method:6} {path}")
        else:
            print(f"[FAIL] {method:6} {path} - NOT FOUND")

    # Check schemas
    print("\n" + "=" * 60)
    print("Schema Verification")
    print("=" * 60)

    schemas_to_check = [
        "UserRegister",
        "Token",
        "UserInfo",
        "InboxItemCreate",
        "InboxItemResponse",
        "CardCreate",
        "CardResponse",
    ]

    for schema_name in schemas_to_check:
        if schema_name in openapi_schema.get('components', {}).get('schemas', {}):
            schema = openapi_schema['components']['schemas'][schema_name]
            print(f"[OK] {schema_name}")
            if 'description' in schema:
                print(f"  Description: {schema['description'][:80]}...")
        else:
            print(f"[FAIL] {schema_name} - NOT FOUND")

    # Save to file
    output_path = "docs/openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"[OK] OpenAPI schema saved to: {output_path}")
    print("=" * 60)

    # Summary
    total_endpoints = sum(len(endpoints) for endpoints in endpoints_by_tag.values())
    print(f"\nTotal Endpoints: {total_endpoints}")
    print(f"Total Tags: {len(endpoints_by_tag)}")

    return openapi_schema


if __name__ == "__main__":
    verify_openapi()
