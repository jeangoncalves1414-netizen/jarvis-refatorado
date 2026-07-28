import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.vision import VisionService
from app.services.browser_agent import BrowserAgent
from app.agent.tools.browser_agent import BrowserAgentTool

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in env.")
        return

    print("Initializing services...")
    vision = VisionService(api_key=api_key)
    # Headless=True so it runs headlessly
    browser = BrowserAgent(headless=True)

    print("Executing BrowserAgentTool...")
    tool = BrowserAgentTool()
    
    # We will tell it to go to google.com and find the search input, but since it's a simple test,
    # let's just make it verify if it can load a page and do 1 step of vision analysis.
    context = {
        "vision": vision,
        "browser": browser
    }
    
    # Let's set a goal that will succeed quickly or we can watch the output
    result = tool.execute(
        args={"goal": "Verifique se a palavra 'Google' está visível na página", "start_url": "https://www.google.com"},
        context=context
    )
    
    print("\nResult:")
    print("OK:", result.ok)
    print("Message:", result.message)

if __name__ == "__main__":
    main()
