"""Quality Assurance Test Questions for Gene.

Run these questions through Gene to verify search and response quality.
Enable internet (🌐) before testing real-time queries.

Usage:
    python tests/qa_test_questions.py  # Prints questions for manual testing
    python tests/qa_test_questions.py --auto  # Runs automated tests (requires app API)
"""

from datetime import datetime

# Test categories with questions and expected behavior
TEST_QUESTIONS = {
    "weather_location": {
        "description": "Weather queries with location - should search and extract temps",
        "requires_internet": True,
        "questions": [
            {
                "q": "What is the temperature in Calgary right now?",
                "expect": "Should search, fetch weather data, return actual temperature in °C",
            },
            {
                "q": "What's the weather forecast for New York this week?",
                "expect": "Should search and provide multi-day forecast",
            },
            {
                "q": "Is it going to rain in Seattle tomorrow?",
                "expect": "Should search and provide precipitation info",
            },
        ],
    },
    
    "weather_followup": {
        "description": "Weather with follow-up context - should combine context",
        "requires_internet": True,
        "questions": [
            {
                "q": "What's the temperature in my area?",
                "followup": "Calgary AB",
                "expect": "After providing location, should search 'temperature Calgary AB'",
            },
            {
                "q": "What's the weather like?",
                "followup": "Toronto",
                "expect": "Should combine 'weather Toronto' and search",
            },
        ],
    },
    
    "current_events": {
        "description": "News and current events - should search for recent info",
        "requires_internet": True,
        "questions": [
            {
                "q": "What's happening in the news today?",
                "expect": "Should search and summarize current headlines",
            },
            {
                "q": "What are the latest tech news?",
                "expect": "Should search for recent tech news",
            },
            {
                "q": "Who won the most recent Super Bowl?",
                "expect": "Should search and provide winner + score",
            },
        ],
    },
    
    "prices_stocks": {
        "description": "Financial data - should search and extract prices",
        "requires_internet": True,
        "questions": [
            {
                "q": "What is the current price of Bitcoin?",
                "expect": "Should search and return current BTC price",
            },
            {
                "q": "What's the stock price of Apple?",
                "expect": "Should search and return AAPL stock price",
            },
            {
                "q": "How much does gold cost per ounce right now?",
                "expect": "Should search and return gold price",
            },
        ],
    },
    
    "local_search": {
        "description": "Location-based searches - should use detected/provided location",
        "requires_internet": True,
        "questions": [
            {
                "q": "What restaurants are near me?",
                "expect": "Should ask for location if not detected, then search",
            },
            {
                "q": "Where is the nearest coffee shop?",
                "expect": "Should search with location context",
            },
            {
                "q": "What time does the Calgary library open?",
                "expect": "Should search for specific local business hours",
            },
        ],
    },
    
    "general_knowledge": {
        "description": "General knowledge - should answer without search",
        "requires_internet": False,
        "questions": [
            {
                "q": "What is the capital of France?",
                "expect": "Should answer 'Paris' without searching",
            },
            {
                "q": "Explain how photosynthesis works",
                "expect": "Should provide educational explanation without search",
            },
            {
                "q": "Write a haiku about programming",
                "expect": "Should generate creative content without search",
            },
        ],
    },
    
    "coding_help": {
        "description": "Programming questions - should answer from knowledge",
        "requires_internet": False,
        "questions": [
            {
                "q": "How do I read a file in Python?",
                "expect": "Should provide Python code example",
            },
            {
                "q": "What's the difference between let and const in JavaScript?",
                "expect": "Should explain JS variable declarations",
            },
            {
                "q": "Write a function to reverse a string",
                "expect": "Should provide working code",
            },
        ],
    },
    
    "retry_and_correction": {
        "description": "Error recovery - should handle retry requests gracefully",
        "requires_internet": True,
        "questions": [
            {
                "q": "What's the temperature?",
                "followup": "You can't get that information?",
                "expect": "Should retry with context if internet enabled",
            },
            {
                "q": "Search for Calgary weather",
                "expect": "Should perform direct search",
            },
        ],
    },
    
    "conversation_context": {
        "description": "Multi-turn conversations - should maintain context",
        "requires_internet": False,
        "questions": [
            {
                "q": "My name is Alex",
                "followup": "What's my name?",
                "expect": "Should remember and respond 'Alex'",
            },
            {
                "q": "Let's talk about Python programming",
                "followup": "What are its main advantages?",
                "expect": "Should understand 'its' refers to Python",
            },
        ],
    },
}

def print_test_suite():
    """Print all test questions for manual testing."""
    print("=" * 70)
    print("GENE QA TEST SUITE")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    print("Instructions:")
    print("1. Launch Gene desktop app")
    print("2. Enable internet (🌐) for real-time queries")
    print("3. Run through each question category")
    print("4. Verify responses match expected behavior")
    print()
    
    total_questions = 0
    
    for category, data in TEST_QUESTIONS.items():
        print("-" * 70)
        print(f"CATEGORY: {category.upper()}")
        print(f"Description: {data['description']}")
        print(f"Requires Internet: {'Yes 🌐' if data['requires_internet'] else 'No'}")
        print("-" * 70)
        
        for i, q_data in enumerate(data["questions"], 1):
            total_questions += 1
            print(f"\n  [{i}] Question: {q_data['q']}")
            if "followup" in q_data:
                print(f"      Follow-up: {q_data['followup']}")
            print(f"      Expected: {q_data['expect']}")
        
        print()
    
    print("=" * 70)
    print(f"TOTAL: {total_questions} test questions across {len(TEST_QUESTIONS)} categories")
    print("=" * 70)

def get_test_questions_list():
    """Return flat list of all test questions."""
    questions = []
    for category, data in TEST_QUESTIONS.items():
        for q_data in data["questions"]:
            questions.append({
                "category": category,
                "requires_internet": data["requires_internet"],
                **q_data
            })
    return questions

if __name__ == "__main__":
    import sys
    
    if "--auto" in sys.argv:
        print("Automated testing not yet implemented.")
        print("Run without --auto for manual test questions.")
    else:
        print_test_suite()
