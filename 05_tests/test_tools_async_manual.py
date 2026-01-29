"""
Manual async tests for tool integration (without pytest-asyncio dependency)
"""

import asyncio
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.pubmed import PubMedTool
from src.tools.base import ToolResult


async def test_pubmed_tool_integration():
    """Test PubMed tool with mock data"""
    print("\nTest: PubMed Tool Integration")
    print("-" * 50)

    # Create tool instance
    tool = PubMedTool(api_key="test_key")

    print(f"✓ Tool name: {tool.name}")
    print(f"✓ Tool domain: {tool.domain}")
    print(f"✓ Tool description: {tool.description}")
    print(f"✓ Rate limit: {tool.requests_per_second} req/s")

    # Note: We can't actually test the execute method without mocking
    # or making real API calls, but we can verify the tool is properly
    # configured and has the expected interface

    assert tool.name == "pubmed"
    assert tool.domain == "biomedical"
    assert tool.requests_per_second == 10  # with API key

    print("\n✓ All assertions passed!")
    return True


async def test_tool_result():
    """Test ToolResult creation"""
    print("\nTest: ToolResult")
    print("-" * 50)

    # Test success result
    success = ToolResult.success_result(
        data={"test": "data"},
        metadata={"key": "value"}
    )

    assert success.success is True
    assert success.data == {"test": "data"}
    assert success.error is None
    print("✓ Success result works")

    # Test error result
    error = ToolResult.error_result(
        error="Test error",
        metadata={"key": "value"}
    )

    assert error.success is False
    assert error.data is None
    assert error.error == "Test error"
    print("✓ Error result works")

    print("\n✓ All assertions passed!")
    return True


async def main():
    """Run all async tests"""
    print("=" * 50)
    print("Async Tool Integration Tests (Manual)")
    print("=" * 50)

    tests = [
        test_tool_result,
        test_pubmed_tool_integration,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            results.append((test.__name__, False))

    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
