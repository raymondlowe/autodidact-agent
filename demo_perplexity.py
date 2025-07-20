#!/usr/bin/env python3
"""
Quick demonstration of the new Perplexity deep research functionality
"""

import sys
import os

# Add the project root to Python path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    """Demonstrate the updated provider information"""
    from utils.providers import get_provider_info, list_available_models
    from utils.config import SUPPORTED_PROVIDERS
    
    print("Provider Information Demo")
    print("=" * 40)
    
    for provider in SUPPORTED_PROVIDERS:
        info = get_provider_info(provider)
        models = list_available_models(provider)
        
        print(f"\n📡 {info['name']} ({provider})")
        print(f"   Description: {info['description']}")
        print(f"   Deep Research: {'✅' if info['supports_deep_research'] else '❌'}")
        print(f"   Web Search: {'✅' if info['supports_web_search'] else '❌'}")
        print(f"   Models: {models}")
        
        if provider == "openrouter":
            print(f"   🔍 Deep Research Model: {models['deep_research']}")
            print(f"   💬 Chat Model: {models['chat']}")


def demo_timeout_config():
    """Demonstrate timeout configuration"""
    from utils.config import PERPLEXITY_DEEP_RESEARCH_TIMEOUT, DEEP_RESEARCH_POLL_INTERVAL
    
    print("\n\nTimeout Configuration Demo")
    print("=" * 40)
    print(f"⏱️  Perplexity Deep Research Timeout: {PERPLEXITY_DEEP_RESEARCH_TIMEOUT}s ({PERPLEXITY_DEEP_RESEARCH_TIMEOUT/60:.1f} minutes)")
    print(f"🔄 OpenAI Poll Interval: {DEEP_RESEARCH_POLL_INTERVAL}s")
    print("\nNote: Perplexity requests are single POST calls that can take 4-5 minutes")
    print("      OpenAI requests use background jobs with polling every 10 seconds")


def demo_job_types():
    """Demonstrate different job ID types"""
    print("\n\nJob ID Types Demo")
    print("=" * 40)
    
    sample_job_ids = [
        ("resp_686d6a4a623481998fe7458cba9f7bd3", "OpenAI background job ID"),
        ("perplexity-abc12345", "Perplexity pseudo job ID"),
        ("chat-def67890", "Fallback chat pseudo job ID")
    ]
    
    for job_id, description in sample_job_ids:
        is_pseudo = job_id.startswith("perplexity-") or job_id.startswith("chat-")
        is_openai = job_id.startswith("resp_")
        
        print(f"🔖 {job_id}")
        print(f"   Type: {description}")
        print(f"   Handling: {'Temp file storage' if is_pseudo else 'OpenAI API polling' if is_openai else 'Legacy'}")


if __name__ == "__main__":
    print("🚀 Perplexity Sonar Deep Research Integration Demo")
    print("This demonstrates the changes made to support Perplexity deep research via OpenRouter")
    
    try:
        demo_provider_info()
        demo_timeout_config()  
        demo_job_types()
        
        print("\n\n🎉 Demo completed successfully!")
        print("\nNext steps:")
        print("1. Configure OpenRouter API key: https://openrouter.ai/keys")
        print("2. Set provider to openrouter in the UI")
        print("3. Start a deep research project")
        print("4. Experience Perplexity Sonar Deep Research!")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()