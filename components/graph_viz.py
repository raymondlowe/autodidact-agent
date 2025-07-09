"""
Graph visualization component for Autodidact
Creates Graphviz diagrams for the knowledge graph
"""

import graphviz
from typing import Dict, List


def calculate_color_gradient(mastery: float) -> str:
    """
    Linear interpolation from white to green based on mastery 0-1
    White: #ffffff (255, 255, 255)
    Green: #26c176 (38, 193, 118)
    """
    # Ensure mastery is in [0, 1]
    mastery = max(0.0, min(1.0, mastery))
    
    r = int(255 - (255 - 38) * mastery)
    g = int(255 - (255 - 193) * mastery)
    b = int(255 - (255 - 118) * mastery)
    
    return f'#{r:02x}{g:02x}{b:02x}'


def create_knowledge_graph(
    nodes: List[Dict], 
    edges: List[Dict], 
    node_mastery: Dict[str, float]
) -> graphviz.Digraph:
    """
    Create a Graphviz diagram for the knowledge graph
    
    Args:
        nodes: List of node dictionaries with 'id' and 'label'
        edges: List of edge dictionaries with 'source', 'target', and optional 'confidence'
        node_mastery: Dictionary mapping node IDs to mastery scores (0-1)
    
    Returns:
        Graphviz Digraph object
    """
    # Create a new directed graph with left-to-right layout
    dot = graphviz.Digraph(engine='dot', comment='Knowledge Graph')
    
    # Configure graph attributes for better layout
    dot.attr(rankdir='LR')  # Left to right layout
    dot.attr('graph', ranksep='1.5', nodesep='0.5', fontname='Arial')
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial', fontsize='12')
    dot.attr('edge', fontname='Arial', fontsize='10')
    
    # Add nodes
    for node in nodes:
        node_id = node['id']
        label = node['label']
        mastery = node_mastery.get(node_id, 0.0)
        
        # Calculate color based on mastery
        color = calculate_color_gradient(mastery)
        
        # Add percentage to label
        display_label = f"{label}\\n({int(mastery * 100)}%)"
        
        dot.node(
            node_id, 
            display_label,
            fillcolor=color,
            fontcolor='black',
            tooltip=node.get('summary', '')
        )
    
    # Add edges
    for edge in edges:
        source = edge['source']
        target = edge['target']
        confidence = edge.get('confidence', 1.0)
        
        # Style based on confidence
        if confidence >= 0.7:
            style = 'solid'
            color = 'black'
        else:
            style = 'dashed'
            color = 'gray'
        
        # Add rationale as edge label if present
        label = edge.get('rationale', '')
        if label and len(label) > 30:
            label = label[:27] + '...'
        
        dot.edge(
            source, 
            target, 
            style=style, 
            color=color,
            label=label if label else None,
            fontsize='9'
        )
    
    return dot


def format_report_with_footnotes(markdown_text: str, footnotes_dict: Dict) -> str:
    """
    Convert [^1] style citations to proper markdown footnotes
    
    Args:
        markdown_text: The main report text with [^n] citations
        footnotes_dict: Dictionary mapping footnote numbers to {title, url}
    
    Returns:
        Formatted markdown with footnotes section
    """
    formatted_text = markdown_text
    
    # Add footnotes section at the end
    if footnotes_dict:
        formatted_text += "\n\n---\n\n## References\n\n"
        
        # Sort footnotes by number
        sorted_footnotes = sorted(
            footnotes_dict.items(), 
            key=lambda x: int(x[0]) if x[0].isdigit() else 0
        )
        
        for num, footnote in sorted_footnotes:
            title = footnote.get('title', 'Unknown')
            url = footnote.get('url', '#')
            
            # Format as markdown footnote
            formatted_text += f"[^{num}]: [{title}]({url})\n\n"
    
    return formatted_text 