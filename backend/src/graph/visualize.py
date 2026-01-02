# Add this to your backend/src/graph/workflow.py or create a new file

from src.graph.workflow import build_graph
from IPython.display import Image, display

def visualize_graph():
    """Generate and display the graph visualization."""
    graph = build_graph()
    
    try:
        # Generate PNG image
        png_data = graph.get_graph().draw_mermaid_png()
        
        # Save to file
        with open("graph_visualization.png", "wb") as f:
            f.write(png_data)
        
        print("✅ Graph saved as 'graph_visualization.png'")
        
        # If running in Jupyter, display it
        try:
            display(Image(png_data))
        except:
            print("💡 Open 'graph_visualization.png' to view the graph")
            
    except Exception as e:
        print(f"❌ Error generating graph: {e}")
        print("\n💡 Make sure you have graphviz installed:")
        print("   - On Ubuntu/Debian: sudo apt-get install graphviz")
        print("   - On macOS: brew install graphviz")
        print("   - On Windows: choco install graphviz")
        print("   - Then: pip install pygraphviz")

if __name__ == "__main__":
    visualize_graph()