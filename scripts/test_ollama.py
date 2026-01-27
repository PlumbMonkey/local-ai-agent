"""Test script for local Ollama LLM."""

import asyncio
import time
from core.llm.ollama import OllamaClient


MODEL = "qwen2.5-coder:7b"


def main():
    client = OllamaClient()
    
    print("=" * 60)
    print("Testing Local AI Model (Ollama)")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n1. Health Check...")
    healthy = client.health_check()
    print(f"   Status: {'✅ OK' if healthy else '❌ FAILED'}")
    
    if not healthy:
        print("   Ollama not running. Start with: ollama serve")
        return
    
    # Test 2: List models
    print("\n2. Available Models...")
    models = client.list_models()
    for m in models:
        print(f"   - {m}")
    
    # Test 3: Simple generation
    print(f"\n3. Testing Generation ({MODEL})...")
    start = time.time()
    
    prompt = "Write a Python function that calculates the factorial of a number. Just code, no explanation."
    response = client.generate(MODEL, prompt)
    
    elapsed = time.time() - start
    print(f"   Time: {elapsed:.2f}s")
    print(f"   Response:\n{'-' * 40}")
    print(response)
    print("-" * 40)
    
    # Test 4: Quick Q&A
    print("\n4. Testing Quick Q&A...")
    start = time.time()
    
    qa_response = client.generate(MODEL, "What is 2 + 2? Answer with just the number.")
    
    elapsed = time.time() - start
    print(f"   Time: {elapsed:.2f}s")
    print(f"   Response: {qa_response.strip()}")
    
    # Test 5: Code completion
    print("\n5. Testing Code Completion...")
    start = time.time()
    
    code_prompt = """Complete this Python code:

def fibonacci(n):
    '''Return the nth Fibonacci number.'''
"""
    code_response = client.generate(MODEL, code_prompt)
    
    elapsed = time.time() - start
    print(f"   Time: {elapsed:.2f}s")
    print(f"   Response:\n{'-' * 40}")
    print(code_response[:500])
    print("-" * 40)
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
