"""Performance benchmark suite for Phase 2 memory system."""

import json
import tempfile
import time
from pathlib import Path

from core.memory.ingest import ChatHistoryIngester
from core.memory.mock_data import generate_mock_conversations
from core.memory.rag import AdvancedRAG
from core.memory.silos import DomainMemory


class Phase2Benchmark:
    """Benchmark Phase 2 memory system performance."""

    def __init__(self):
        self.results = {}

    def benchmark_ingest_speed(self, count: int = 1000):
        """Measure chat history ingestion throughput."""
        print(f"\n📊 Benchmark 1: Ingestion Speed ({count} conversations)")
        print("-" * 60)

        # Generate mock data
        print("  • Generating mock conversations...", end=" ", flush=True)
        conversations = generate_mock_conversations(count=count)
        print("✓")

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"conversations": conversations}, f)
            temp_file = f.name

        try:
            # Measure ingestion time
            ingester = ChatHistoryIngester()
            print(f"  • Ingesting {count} conversations...", end=" ", flush=True)
            start = time.time()
            count_ingested = ingester.ingest_and_store(temp_file)
            elapsed = time.time() - start

            throughput = count_ingested / elapsed if elapsed > 0 else 0
            self.results["ingest_speed"] = {
                "conversations": count_ingested,
                "elapsed_seconds": elapsed,
                "throughput_per_sec": throughput,
            }

            print("✓")
            print(f"  ✓ Ingested: {count_ingested} conversations")
            print(f"  ✓ Time: {elapsed:.2f}s")
            print(f"  ✓ Throughput: {throughput:.0f} conversations/sec")
            print(f"  ✓ Target: >100/sec | Actual: {'✓' if throughput >= 100 else '✗'}")

        finally:
            Path(temp_file).unlink()

    def benchmark_query_latency(self, count: int = 100):
        """Measure query latency and consistency."""
        print(f"\n📊 Benchmark 2: Query Latency ({count} queries)")
        print("-" * 60)

        # Setup: Create some conversations
        print("  • Setting up test data...", end=" ", flush=True)
        conversations = generate_mock_conversations(count=500, domains=["coding"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"conversations": conversations}, f)
            temp_file = f.name

        try:
            ingester = ChatHistoryIngester()
            ingester.ingest_and_store(temp_file)
            print("✓")

            # Measure query latencies
            rag = AdvancedRAG()
            queries = [
                "How to debug Python?",
                "What's a good async pattern?",
                "How to handle timeouts?",
                "Best practice for error handling?",
                "How to optimize performance?",
            ]

            latencies = []
            print(f"  • Running {count} queries...", end=" ", flush=True)

            for i in range(count):
                query = queries[i % len(queries)]
                start = time.time()
                results = rag.query(query, domain="coding", top_k=5)
                elapsed = (time.time() - start) * 1000  # Convert to ms

                latencies.append(elapsed)

                if (i + 1) % 20 == 0:
                    print(f"\n    ({i + 1}/{count})", end=" ", flush=True)

            print("✓")

            # Calculate statistics
            latencies_sorted = sorted(latencies)
            p50 = latencies_sorted[int(len(latencies) * 0.5)]
            p95 = latencies_sorted[int(len(latencies) * 0.95)]
            p99 = latencies_sorted[int(len(latencies) * 0.99)]
            avg = sum(latencies) / len(latencies)

            self.results["query_latency"] = {
                "query_count": count,
                "avg_ms": avg,
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99,
            }

            print(f"  ✓ Avg Latency: {avg:.0f}ms")
            print(f"  ✓ P50 (median): {p50:.0f}ms")
            print(f"  ✓ P95 (95th %ile): {p95:.0f}ms")
            print(f"  ✓ P99 (99th %ile): {p99:.0f}ms")
            print(f"  ✓ Target: <500ms p95 | Actual: {'✓' if p95 < 500 else '✗'}")

        finally:
            # Cleanup
            memory = DomainMemory(domain="coding")
            memory.clear()
            Path(temp_file).unlink()

    def benchmark_accuracy(self, count: int = 50):
        """Measure retrieval accuracy and relevance."""
        print(f"\n📊 Benchmark 3: Retrieval Accuracy ({count} queries)")
        print("-" * 60)

        # Setup: Create conversations with clear topics
        print("  • Setting up test data with known topics...", end=" ", flush=True)
        conversations = []

        # Add async-related conversations
        for i in range(25):
            conversations.extend(
                [
                    {
                        "id": f"async-{i}-1",
                        "domain": "coding",
                        "messages": [
                            {"role": "user", "content": "How to use async/await?"},
                            {
                                "role": "assistant",
                                "content": "Use async def for coroutines and await for operations",
                            },
                        ],
                    },
                    {
                        "id": f"async-{i}-2",
                        "domain": "coding",
                        "messages": [
                            {
                                "role": "user",
                                "content": "How to handle async timeouts?",
                            },
                            {
                                "role": "assistant",
                                "content": "Use asyncio.wait_for() with timeout parameter",
                            },
                        ],
                    },
                ]
            )

        # Add error handling conversations
        for i in range(25):
            conversations.extend(
                [
                    {
                        "id": f"error-{i}-1",
                        "domain": "coding",
                        "messages": [
                            {"role": "user", "content": "How to handle errors?"},
                            {
                                "role": "assistant",
                                "content": "Use try/except blocks and logging",
                            },
                        ],
                    },
                    {
                        "id": f"error-{i}-2",
                        "domain": "coding",
                        "messages": [
                            {"role": "user", "content": "Best practices for exceptions?"},
                            {
                                "role": "assistant",
                                "content": "Catch specific exceptions and use context managers",
                            },
                        ],
                    },
                ]
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"conversations": conversations}, f)
            temp_file = f.name

        try:
            ingester = ChatHistoryIngester()
            ingester.ingest_and_store(temp_file)
            print("✓")

            # Run targeted queries
            rag = AdvancedRAG()

            # Async queries should return async results
            async_queries = [
                ("How to use async?", "async"),
                ("What about timeouts?", "async"),
                ("Tell me about coroutines", "async"),
            ]

            # Error queries should return error results
            error_queries = [
                ("How to handle errors?", "error"),
                ("Exception handling tips", "error"),
                ("Try/catch best practices", "error"),
            ]

            relevant_count = 0
            total_count = 0

            print(f"  • Testing {len(async_queries) + len(error_queries)} targeted queries...")

            # Test async queries
            for query, expected_topic in async_queries:
                results = rag.query(query, domain="coding", top_k=5)
                total_count += len(results)

                for result in results:
                    if expected_topic in result["content"].lower():
                        relevant_count += 1

            # Test error queries
            for query, expected_topic in error_queries:
                results = rag.query(query, domain="coding", top_k=5)
                total_count += len(results)

                for result in results:
                    if expected_topic in result["content"].lower():
                        relevant_count += 1

            accuracy = (relevant_count / total_count * 100) if total_count > 0 else 0

            self.results["accuracy"] = {
                "queries": len(async_queries) + len(error_queries),
                "total_results": total_count,
                "relevant_count": relevant_count,
                "accuracy_percent": accuracy,
            }

            print(f"  ✓ Accuracy: {accuracy:.0f}% ({relevant_count}/{total_count})")
            print(f"  ✓ Target: >80% | Actual: {'✓' if accuracy >= 80 else '✗'}")

        finally:
            # Cleanup
            memory = DomainMemory(domain="coding")
            memory.clear()
            Path(temp_file).unlink()

    def benchmark_memory_usage(self, count: int = 1000):
        """Estimate memory usage for large collections."""
        import sys

        print(f"\n📊 Benchmark 4: Memory Usage (est. for {count} conversations)")
        print("-" * 60)

        print("  • Generating and ingesting data...", end=" ", flush=True)
        conversations = generate_mock_conversations(count=count)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"conversations": conversations}, f)
            temp_file = f.name

        try:
            ingester = ChatHistoryIngester()
            ingester.ingest_and_store(temp_file)
            print("✓")

            # Get memory stats
            memory = DomainMemory(domain="coding")
            stats = memory.get_stats()

            print(f"  ✓ Documents stored: {stats.get('total_documents', 'N/A')}")
            print(f"  ✓ Collection size: {stats.get('collection_size', 'N/A')} bytes")

            # Rough estimate based on average document size
            if stats.get("collection_size"):
                mb_per_1000 = stats["collection_size"] / (count / 1000) / 1024 / 1024
                estimated_2gb = 2048 / mb_per_1000 * 1000
                print(
                    f"  ✓ Est. for 2GB: {estimated_2gb:.0f} conversations"
                )
                print(f"  ✓ Target: 10k conversations in <2GB | Actual: {'✓' if estimated_2gb >= 10000 else '✗'}")

            self.results["memory_usage"] = {
                "collection_size_bytes": stats.get("collection_size", 0),
                "total_documents": stats.get("total_documents", 0),
            }

        finally:
            memory = DomainMemory(domain="coding")
            memory.clear()
            Path(temp_file).unlink()

    def run_all(self):
        """Run all benchmarks."""
        print("\n" + "=" * 60)
        print("🚀 Phase 2 Memory System Performance Benchmark")
        print("=" * 60)

        try:
            self.benchmark_ingest_speed(count=1000)
            self.benchmark_query_latency(count=100)
            self.benchmark_accuracy(count=50)
            self.benchmark_memory_usage(count=1000)

            # Summary
            print("\n" + "=" * 60)
            print("📈 Benchmark Summary")
            print("=" * 60)

            # Check targets
            targets_met = 0
            total_targets = 0

            if self.results.get("ingest_speed"):
                throughput = self.results["ingest_speed"]["throughput_per_sec"]
                total_targets += 1
                if throughput >= 100:
                    targets_met += 1
                print(f"  ✓ Ingestion: {throughput:.0f}/sec (target: 100/sec)")

            if self.results.get("query_latency"):
                p95 = self.results["query_latency"]["p95_ms"]
                total_targets += 1
                if p95 < 500:
                    targets_met += 1
                print(f"  ✓ Query Latency P95: {p95:.0f}ms (target: <500ms)")

            if self.results.get("accuracy"):
                acc = self.results["accuracy"]["accuracy_percent"]
                total_targets += 1
                if acc >= 80:
                    targets_met += 1
                print(f"  ✓ Retrieval Accuracy: {acc:.0f}% (target: >80%)")

            if self.results.get("memory_usage"):
                docs = self.results["memory_usage"]["total_documents"]
                print(f"  ✓ Memory: {docs} documents stored")

            print("\n" + "=" * 60)
            print(f"✓ Performance Targets Met: {targets_met}/{total_targets}")
            print("=" * 60)

        except Exception as e:
            print(f"\n❌ Benchmark failed: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    benchmark = Phase2Benchmark()
    benchmark.run_all()
