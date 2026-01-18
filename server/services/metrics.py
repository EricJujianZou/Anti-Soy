from datetime import datetime
from collections import defaultdict
import json

class MetricsCalculator:
    
    @staticmethod
    def calculate_commit_density(commits):
        if not commits:
             return {"variance": 0, "score": 0, "interpretation": "No commits"}
        
        timestamps = []
        for c in commits:
            ts = c.get("committedDate")
            if ts:
                # Format: 2023-10-25T12:00:00Z
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(dt.timestamp())
                except ValueError:
                    continue
        
        if not timestamps:
            return {"variance": 0, "score": 0, "interpretation": "No valid timestamps"}

        # Group by day to see burstiness
        daily_counts = defaultdict(int)
        for t in timestamps:
             dt = datetime.fromtimestamp(t)
             day_key = dt.strftime("%Y-%m-%d")
             daily_counts[day_key] += 1
             
        counts = list(daily_counts.values())
        max_daily = max(counts) if counts else 0
        total = len(timestamps)
        
        # Burst ratio: Max commits in a single day / Total commits analyzed
        # If I did 50 commits and 45 were on one day -> Ratio 0.9 -> Score 10 (Bad/Bursty)
        # If I did 50 commits and max daily was 5 -> Ratio 0.1 -> Score 90 (Consistent)
        burst_ratio = max_daily / total if total > 0 else 0
        
        score = int((1 - burst_ratio) * 100)
        
        return {
            "burst_ratio": round(burst_ratio, 2),
            "score": score,
            "interpretation": "Consistent" if score > 50 else "Bursty/Clustered"
        }

    @staticmethod
    def calculate_commit_lines(commits):
        if not commits:
             return {"avg_size": 0, "massive_count": 0, "score": 0}
             
        massive_threshold = 10000
        massive_count = 0
        total_size = 0
        
        for c in commits:
            # additions + deletions
            size = c.get("additions", 0) + c.get("deletions", 0)
            total_size += size
            if size > massive_threshold:
                massive_count += 1
                
        avg_size = total_size / len(commits)
        
        # Scoring: 
        # Start at 100
        # -25 for each massive commit
        # -20 if avg size is large (>1000)
        score = 100
        score -= (massive_count * 25)
        if avg_size > 1000:
             score -= 20
        
        return {
            "avg_size": round(avg_size, 1),
            "massive_count": massive_count,
            "score": max(0, score)
        }
