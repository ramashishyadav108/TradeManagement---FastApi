"""
Performance Benchmarking Suite for Matching Engine

Comprehensive benchmarks to measure:
- Order submission latency
- Matching engine throughput
- WebSocket broadcast performance
- Memory usage under load
- Concurrent client handling
"""

import time
import statistics
import json
import psutil
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Any
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.matching_engine import MatchingEngine
from backend.core.order import Order, OrderType, OrderSide


@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""
    name: str
    total_operations: int
    duration_seconds: float
    operations_per_second: float
    latency_p50_ms: float
    latency_p90_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    min_latency_ms: float
    max_latency_ms: float
    memory_before_mb: float
    memory_after_mb: float
    memory_peak_mb: float
    cpu_percent: float
    success_count: int
    error_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_markdown(self) -> str:
        """Generate markdown report"""
        return f"""
## {self.name}

### Summary
- **Total Operations**: {self.total_operations:,}
- **Duration**: {self.duration_seconds:.2f} seconds
- **Throughput**: {self.operations_per_second:,.2f} ops/sec
- **Success Rate**: {self.success_count / self.total_operations * 100:.2f}%

### Latency Percentiles
| Metric | Value (ms) | Target | Status |
|--------|-----------|--------|--------|
| P50 (Median) | {self.latency_p50_ms:.3f} | <1.0 | {'✅ PASS' if self.latency_p50_ms < 1.0 else '❌ FAIL'} |
| P90 | {self.latency_p90_ms:.3f} | <1.0 | {'✅ PASS' if self.latency_p90_ms < 1.0 else '❌ FAIL'} |
| P95 | {self.latency_p95_ms:.3f} | <1.0 | {'✅ PASS' if self.latency_p95_ms < 1.0 else '⚠️ WARNING'} |
| P99 | {self.latency_p99_ms:.3f} | <5.0 | {'✅ PASS' if self.latency_p99_ms < 5.0 else '⚠️ WARNING'} |
| Min | {self.min_latency_ms:.3f} | - | - |
| Max | {self.max_latency_ms:.3f} | - | - |

### Resource Usage
- **Memory Before**: {self.memory_before_mb:.2f} MB
- **Memory After**: {self.memory_after_mb:.2f} MB
- **Memory Peak**: {self.memory_peak_mb:.2f} MB
- **Memory Delta**: {self.memory_after_mb - self.memory_before_mb:.2f} MB
- **CPU Usage**: {self.cpu_percent:.1f}%

### Results
- **Successful**: {self.success_count:,}
- **Errors**: {self.error_count:,}
"""


class PerformanceBenchmark:
    """Comprehensive performance benchmarking for matching engine"""
    
    def __init__(self):
        self.engine = MatchingEngine()
        self.process = psutil.Process(os.getpid())
        self.results: List[BenchmarkResult] = []
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024
    
    def _get_cpu_percent(self) -> float:
        """Get current CPU usage percentage"""
        return self.process.cpu_percent(interval=0.1)
    
    def _calculate_latencies(self, latencies: List[float]) -> Dict[str, float]:
        """Calculate latency percentiles in milliseconds"""
        if not latencies:
            return {
                'p50': 0.0, 'p90': 0.0, 'p95': 0.0, 'p99': 0.0,
                'min': 0.0, 'max': 0.0
            }
        
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        return {
            'p50': sorted_latencies[int(n * 0.50)] * 1000,
            'p90': sorted_latencies[int(n * 0.90)] * 1000,
            'p95': sorted_latencies[int(n * 0.95)] * 1000,
            'p99': sorted_latencies[int(n * 0.99)] * 1000,
            'min': min(latencies) * 1000,
            'max': max(latencies) * 1000
        }
    
    def benchmark_order_submission(self, num_orders: int = 10000, 
                                   order_type: OrderType = OrderType.LIMIT) -> BenchmarkResult:
        """
        Benchmark order submission performance
        
        Args:
            num_orders: Number of orders to submit
            order_type: Type of orders to submit
            
        Returns:
            BenchmarkResult with performance metrics
        """
        print(f"\n{'='*80}")
        print(f"Benchmarking {order_type.value.upper()} Order Submission ({num_orders:,} orders)")
        print(f"{'='*80}\n")
        
        # Reset engine
        self.engine = MatchingEngine()
        
        # Measure memory before
        memory_before = self._get_memory_usage()
        peak_memory = memory_before
        
        latencies = []
        success_count = 0
        error_count = 0
        
        # Start benchmark
        start_time = time.time()
        
        for i in range(num_orders):
            try:
                # Alternate buy/sell and vary prices
                side = OrderSide.BUY if i % 2 == 0 else OrderSide.SELL
                base_price = 50000
                price_variation = (i % 100) * 10
                price = Decimal(str(base_price + price_variation))
                quantity = Decimal(str(0.1 + (i % 10) * 0.1))
                
                # Create order
                order = Order(
                    symbol="BTC-USDT",
                    order_type=order_type,
                    side=side,
                    quantity=quantity,
                    price=price if order_type != OrderType.MARKET else None
                )
                
                # Measure single order latency
                order_start = time.time()
                self.engine.submit_order(order)
                order_end = time.time()
                
                latencies.append(order_end - order_start)
                success_count += 1
                
                # Track peak memory
                current_memory = self._get_memory_usage()
                peak_memory = max(peak_memory, current_memory)
                
            except Exception as e:
                error_count += 1
                print(f"Error submitting order {i}: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Measure final state
        memory_after = self._get_memory_usage()
        cpu_percent = self._get_cpu_percent()
        
        # Calculate metrics
        latency_stats = self._calculate_latencies(latencies)
        ops_per_second = num_orders / duration if duration > 0 else 0
        
        result = BenchmarkResult(
            name=f"{order_type.value.upper()} Order Submission Benchmark",
            total_operations=num_orders,
            duration_seconds=duration,
            operations_per_second=ops_per_second,
            latency_p50_ms=latency_stats['p50'],
            latency_p90_ms=latency_stats['p90'],
            latency_p95_ms=latency_stats['p95'],
            latency_p99_ms=latency_stats['p99'],
            min_latency_ms=latency_stats['min'],
            max_latency_ms=latency_stats['max'],
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            memory_peak_mb=peak_memory,
            cpu_percent=cpu_percent,
            success_count=success_count,
            error_count=error_count
        )
        
        self.results.append(result)
        self._print_result(result)
        
        return result
    
    def benchmark_matching_latency(self) -> Dict[str, BenchmarkResult]:
        """
        Benchmark matching latency for different order types
        
        Returns:
            Dictionary mapping order type to benchmark results
        """
        print(f"\n{'='*80}")
        print("Benchmarking Matching Engine Latency by Order Type")
        print(f"{'='*80}\n")
        
        results = {}
        
        # Test each order type
        for order_type in [OrderType.LIMIT, OrderType.MARKET, OrderType.IOC, OrderType.FOK]:
            result = self.benchmark_order_submission(
                num_orders=5000,
                order_type=order_type
            )
            results[order_type.value] = result
        
        return results
    
    def benchmark_concurrent_load(self, num_clients: int = 10, 
                                  orders_per_client: int = 1000) -> BenchmarkResult:
        """
        Benchmark concurrent client load
        
        Args:
            num_clients: Number of concurrent clients
            orders_per_client: Orders submitted by each client
            
        Returns:
            BenchmarkResult with concurrent performance metrics
        """
        print(f"\n{'='*80}")
        print(f"Benchmarking Concurrent Load ({num_clients} clients, {orders_per_client} orders each)")
        print(f"{'='*80}\n")
        
        # Reset engine
        self.engine = MatchingEngine()
        
        memory_before = self._get_memory_usage()
        peak_memory = memory_before
        
        all_latencies = []
        total_success = 0
        total_errors = 0
        
        def submit_orders_for_client(client_id: int) -> tuple:
            """Submit orders from a single client"""
            latencies = []
            success = 0
            errors = 0
            
            for i in range(orders_per_client):
                try:
                    side = OrderSide.BUY if (client_id + i) % 2 == 0 else OrderSide.SELL
                    price = Decimal(str(50000 + (i % 100) * 10))
                    quantity = Decimal(str(0.1 * (1 + i % 5)))
                    
                    order = Order(
                        symbol="BTC-USDT",
                        order_type=OrderType.LIMIT,
                        side=side,
                        quantity=quantity,
                        price=price
                    )
                    
                    order_start = time.time()
                    self.engine.submit_order(order)
                    order_end = time.time()
                    
                    latencies.append(order_end - order_start)
                    success += 1
                    
                except Exception as e:
                    errors += 1
            
            return latencies, success, errors
        
        # Start concurrent benchmark
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            futures = [
                executor.submit(submit_orders_for_client, i)
                for i in range(num_clients)
            ]
            
            for future in as_completed(futures):
                latencies, success, errors = future.result()
                all_latencies.extend(latencies)
                total_success += success
                total_errors += errors
                
                # Track memory
                current_memory = self._get_memory_usage()
                peak_memory = max(peak_memory, current_memory)
        
        end_time = time.time()
        duration = end_time - start_time
        
        memory_after = self._get_memory_usage()
        cpu_percent = self._get_cpu_percent()
        
        total_operations = num_clients * orders_per_client
        latency_stats = self._calculate_latencies(all_latencies)
        ops_per_second = total_operations / duration if duration > 0 else 0
        
        result = BenchmarkResult(
            name=f"Concurrent Load Benchmark ({num_clients} clients)",
            total_operations=total_operations,
            duration_seconds=duration,
            operations_per_second=ops_per_second,
            latency_p50_ms=latency_stats['p50'],
            latency_p90_ms=latency_stats['p90'],
            latency_p95_ms=latency_stats['p95'],
            latency_p99_ms=latency_stats['p99'],
            min_latency_ms=latency_stats['min'],
            max_latency_ms=latency_stats['max'],
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            memory_peak_mb=peak_memory,
            cpu_percent=cpu_percent,
            success_count=total_success,
            error_count=total_errors
        )
        
        self.results.append(result)
        self._print_result(result)
        
        return result
    
    def benchmark_memory_usage(self, num_orders: int = 100000) -> BenchmarkResult:
        """
        Benchmark memory usage with large number of orders
        
        Args:
            num_orders: Number of orders to test with
            
        Returns:
            BenchmarkResult focused on memory metrics
        """
        print(f"\n{'='*80}")
        print(f"Benchmarking Memory Usage ({num_orders:,} orders)")
        print(f"{'='*80}\n")
        
        # Reset engine
        self.engine = MatchingEngine()
        
        memory_before = self._get_memory_usage()
        peak_memory = memory_before
        
        latencies = []
        success_count = 0
        
        start_time = time.time()
        
        # Submit orders to fill the order book
        for i in range(num_orders):
            side = OrderSide.BUY if i % 2 == 0 else OrderSide.SELL
            # Wide price range to avoid matching
            price_offset = 10000 if side == OrderSide.BUY else 20000
            price = Decimal(str(40000 + price_offset + (i % 1000)))
            quantity = Decimal(str(0.1 + (i % 10) * 0.01))
            
            order = Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=side,
                quantity=quantity,
                price=price
            )
            
            order_start = time.time()
            self.engine.submit_order(order)
            order_end = time.time()
            
            latencies.append(order_end - order_start)
            success_count += 1
            
            # Sample memory every 1000 orders
            if i % 1000 == 0:
                current_memory = self._get_memory_usage()
                peak_memory = max(peak_memory, current_memory)
                print(f"  Orders: {i:,} | Memory: {current_memory:.2f} MB", end='\r')
        
        end_time = time.time()
        duration = end_time - start_time
        
        memory_after = self._get_memory_usage()
        cpu_percent = self._get_cpu_percent()
        
        print(f"\n  Final: {num_orders:,} orders | Memory: {memory_after:.2f} MB")
        
        # Calculate average order size in memory
        memory_per_order = (memory_after - memory_before) / num_orders if num_orders > 0 else 0
        print(f"  Average memory per order: {memory_per_order * 1024:.2f} KB")
        
        latency_stats = self._calculate_latencies(latencies)
        ops_per_second = num_orders / duration if duration > 0 else 0
        
        result = BenchmarkResult(
            name=f"Memory Usage Benchmark ({num_orders:,} active orders)",
            total_operations=num_orders,
            duration_seconds=duration,
            operations_per_second=ops_per_second,
            latency_p50_ms=latency_stats['p50'],
            latency_p90_ms=latency_stats['p90'],
            latency_p95_ms=latency_stats['p95'],
            latency_p99_ms=latency_stats['p99'],
            min_latency_ms=latency_stats['min'],
            max_latency_ms=latency_stats['max'],
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            memory_peak_mb=peak_memory,
            cpu_percent=cpu_percent,
            success_count=success_count,
            error_count=0
        )
        
        self.results.append(result)
        self._print_result(result)
        
        # Target: <500MB for 100k orders
        if num_orders >= 100000:
            target_memory = 500.0
            actual_memory = memory_after - memory_before
            status = "✅ PASS" if actual_memory < target_memory else "❌ FAIL"
            print(f"\n  Memory Target Check: {actual_memory:.2f} MB / {target_memory} MB - {status}")
        
        return result
    
    def _print_result(self, result: BenchmarkResult):
        """Print benchmark result summary"""
        print(f"\n{'─'*80}")
        print(f"RESULT: {result.name}")
        print(f"{'─'*80}")
        print(f"  Throughput:     {result.operations_per_second:>12,.2f} ops/sec")
        print(f"  Latency P50:    {result.latency_p50_ms:>12.3f} ms")
        print(f"  Latency P95:    {result.latency_p95_ms:>12.3f} ms")
        print(f"  Latency P99:    {result.latency_p99_ms:>12.3f} ms")
        print(f"  Memory Delta:   {result.memory_after_mb - result.memory_before_mb:>12.2f} MB")
        print(f"  Success Rate:   {result.success_count / result.total_operations * 100:>12.1f}%")
        print(f"{'─'*80}\n")
    
    def generate_report(self, output_file: str = "benchmark_report"):
        """
        Generate comprehensive benchmark report
        
        Args:
            output_file: Base filename for report (without extension)
        """
        # Generate JSON report
        json_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "system_info": {
                "python_version": sys.version,
                "cpu_count": psutil.cpu_count(),
                "total_memory_mb": psutil.virtual_memory().total / 1024 / 1024
            },
            "results": [result.to_dict() for result in self.results]
        }
        
        json_file = f"{output_file}.json"
        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        print(f"✅ JSON report saved to: {json_file}")
        
        # Generate Markdown report
        md_content = f"""# Performance Benchmark Report

**Generated**: {time.strftime("%Y-%m-%d %H:%M:%S")}

## System Information
- **Python Version**: {sys.version.split()[0]}
- **CPU Cores**: {psutil.cpu_count()}
- **Total Memory**: {psutil.virtual_memory().total / 1024 / 1024:.2f} MB

## Executive Summary

| Benchmark | Throughput (ops/sec) | P95 Latency (ms) | Memory Delta (MB) | Status |
|-----------|---------------------|------------------|-------------------|--------|
"""
        
        for result in self.results:
            # Determine status based on targets
            throughput_ok = result.operations_per_second > 1000
            latency_ok = result.latency_p95_ms < 1.0
            status = "✅ PASS" if throughput_ok and latency_ok else "⚠️ WARNING"
            
            md_content += f"| {result.name} | {result.operations_per_second:,.0f} | {result.latency_p95_ms:.3f} | {result.memory_after_mb - result.memory_before_mb:.2f} | {status} |\n"
        
        md_content += "\n## Detailed Results\n"
        
        for result in self.results:
            md_content += result.to_markdown()
            md_content += "\n---\n"
        
        # Add target comparison
        md_content += """
## Target Benchmarks Comparison

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| Limit order processing (P95) | <1ms | {limit_p95:.3f}ms | {limit_status} |
| Market order processing (P95) | <5ms | {market_p95:.3f}ms | {market_status} |
| Throughput | >1000 ops/sec | {throughput:.0f} ops/sec | {throughput_status} |
| Memory (100k orders) | <500MB | {memory:.2f}MB | {memory_status} |

## Recommendations

{recommendations}
"""
        
        # Find specific results for targets
        limit_result = next((r for r in self.results if "LIMIT" in r.name and "Order Submission" in r.name), None)
        market_result = next((r for r in self.results if "MARKET" in r.name), None)
        memory_result = next((r for r in self.results if "Memory Usage" in r.name), None)
        
        limit_p95 = limit_result.latency_p95_ms if limit_result else 0
        market_p95 = market_result.latency_p95_ms if market_result else 0
        throughput = max((r.operations_per_second for r in self.results), default=0)
        memory_delta = memory_result.memory_after_mb - memory_result.memory_before_mb if memory_result else 0
        
        recommendations = []
        if limit_p95 >= 1.0:
            recommendations.append("- ⚠️ Limit order latency exceeds target. Consider optimizing order book insertion.")
        if market_p95 >= 5.0:
            recommendations.append("- ⚠️ Market order latency exceeds target. Review matching algorithm efficiency.")
        if throughput < 1000:
            recommendations.append("- ⚠️ Throughput below target. Profile code for bottlenecks.")
        if memory_delta >= 500:
            recommendations.append("- ⚠️ Memory usage exceeds target. Review data structure memory efficiency.")
        
        if not recommendations:
            recommendations.append("- ✅ All targets met! System performing within specifications.")
        
        md_content = md_content.format(
            limit_p95=limit_p95,
            market_p95=market_p95,
            throughput=throughput,
            memory=memory_delta,
            limit_status="✅ PASS" if limit_p95 < 1.0 else "❌ FAIL",
            market_status="✅ PASS" if market_p95 < 5.0 else "❌ FAIL",
            throughput_status="✅ PASS" if throughput > 1000 else "❌ FAIL",
            memory_status="✅ PASS" if memory_delta < 500 else "❌ FAIL",
            recommendations="\n".join(recommendations)
        )
        
        md_file = f"{output_file}.md"
        with open(md_file, 'w') as f:
            f.write(md_content)
        
        print(f"✅ Markdown report saved to: {md_file}")
    
    def run_full_benchmark_suite(self):
        """Run complete benchmark suite"""
        print("\n" + "="*80)
        print("COMPREHENSIVE PERFORMANCE BENCHMARK SUITE")
        print("="*80)
        
        # 1. Order submission benchmarks
        print("\n📊 Phase 1: Order Submission Benchmarks")
        self.benchmark_order_submission(num_orders=10000, order_type=OrderType.LIMIT)
        self.benchmark_order_submission(num_orders=10000, order_type=OrderType.MARKET)
        
        # 2. Matching latency by order type
        print("\n📊 Phase 2: Matching Latency Analysis")
        self.benchmark_matching_latency()
        
        # 3. Concurrent load
        print("\n📊 Phase 3: Concurrent Load Testing")
        self.benchmark_concurrent_load(num_clients=10, orders_per_client=1000)
        
        # 4. Memory usage
        print("\n📊 Phase 4: Memory Usage Analysis")
        self.benchmark_memory_usage(num_orders=100000)
        
        # 5. Generate reports
        print("\n📊 Phase 5: Generating Reports")
        self.generate_report()
        
        print("\n" + "="*80)
        print("BENCHMARK SUITE COMPLETE!")
        print("="*80)
        print(f"\nTotal benchmarks run: {len(self.results)}")
        print(f"Reports generated: benchmark_report.json, benchmark_report.md")


def main():
    """Main entry point for benchmark script"""
    benchmark = PerformanceBenchmark()
    benchmark.run_full_benchmark_suite()


if __name__ == "__main__":
    main()
