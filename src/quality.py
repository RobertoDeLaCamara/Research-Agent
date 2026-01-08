import re
from typing import List

def score_content_quality(content: str) -> float:
    """Score content quality based on various factors."""
    if not content:
        return 0.0
        
    score = 0.0
    content_lower = content.lower()
    
    # Length scoring (0-0.3)
    if len(content) > 1000:
        score += 0.3
    elif len(content) > 500:
        score += 0.2
    elif len(content) > 100:
        score += 0.1
    
    # Source/URL presence (0-0.2)
    url_count = len(re.findall(r'https?://\S+', content))
    if url_count >= 3:
        score += 0.2
    elif url_count >= 1:
        score += 0.1
    
    # Academic/research keywords (0-0.3)
    research_keywords = ['study', 'research', 'analysis', 'findings', 'methodology', 
                        'experiment', 'data', 'results', 'conclusion', 'evidence']
    keyword_matches = sum(1 for keyword in research_keywords if keyword in content_lower)
    if keyword_matches >= 5:
        score += 0.3
    elif keyword_matches >= 3:
        score += 0.2
    elif keyword_matches >= 1:
        score += 0.1
    
    # Structure indicators (0-0.2)
    structure_indicators = ['\n\n', '##', '###', '- ', '* ', '1.', '2.']
    structure_count = sum(1 for indicator in structure_indicators if indicator in content)
    if structure_count >= 3:
        score += 0.2
    elif structure_count >= 1:
        score += 0.1
    
    return min(score, 1.0)

def filter_quality_content(content_list: List[dict], min_score: float = 0.3) -> List[dict]:
    """Filter content based on quality score."""
    filtered = []
    
    for item in content_list:
        content = item.get('content', '') or item.get('summary', '') or item.get('description', '')
        quality_score = score_content_quality(content)
        
        if quality_score >= min_score:
            item['quality_score'] = quality_score
            filtered.append(item)
    
    # Sort by quality score (highest first)
    return sorted(filtered, key=lambda x: x.get('quality_score', 0), reverse=True)

def get_content_summary(content: str) -> dict:
    """Get summary statistics about content."""
    return {
        'length': len(content),
        'word_count': len(content.split()),
        'url_count': len(re.findall(r'https?://\S+', content)),
        'quality_score': score_content_quality(content)
    }
