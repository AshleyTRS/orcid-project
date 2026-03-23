"""
Example script: Generate publication analytics and statistics reports.

Demonstrates how to use the analytics module to compute various publication
metrics and generate reports suitable for visualization or institutional reporting.

Usage:
    python scripts/analyze_publications.py
"""
import sys
import os
from pathlib import Path
import json
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.db.MongoConnection import MongoConnection
from src.analytics.aggregations import (
    publications_per_year,
    publications_per_institution_per_year,
    publications_per_type,
    top_authors,
    author_contributor_analysis,
    publication_metrics_summary
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_analysis_report(mongo_uri: str, db_name: str, output_file: str = None):
    """
    Generate a comprehensive publication analysis report.
    
    Args:
        mongo_uri: MongoDB connection string
        db_name: Database name
        output_file: Optional path to save report as JSON
    """
    logger.info("=" * 70)
    logger.info("PUBLICATION ANALYTICS REPORT")
    logger.info("=" * 70)
    
    mongo = None
    
    try:
        # Connect to database
        mongo = MongoConnection(mongo_uri, db_name)
        
        # 1. Publication metrics summary
        logger.info("\nSUMMARY METRICS")
        logger.info("-" * 70)
        summary = publication_metrics_summary(mongo.db)
        
        print(f"  Total Publications: {summary['total_publications']:,}")
        print(f"  Unique Institutions: {summary['total_institutions']}")
        print(f"  Publication Types: {summary['publication_types']}")
        print(f"  Year Range: {summary['year_range']['min']} - {summary['year_range']['max']}")
        print(f"  Average Authors/Publication: {summary['avg_authors_per_publication']}")
        print(f"  Author Range: {summary['min_authors']} - {summary['max_authors']}")
        
        # 2. Publications per year
        logger.info("\nPUBLICATIONS PER YEAR")
        logger.info("-" * 70)
        yearly_stats = publications_per_year(mongo.db)
        
        for stat in yearly_stats[-10:]:  # Last 10 years
            bar = "█" * (stat['count'] // 100)
            print(f"  {stat['year']}: {stat['count']:>6} {bar}")
        
        # 3. Publications by type
        logger.info("\nPUBLICATIONS BY TYPE")
        logger.info("-" * 70)
        type_stats = publications_per_type(mongo.db)
        
        for stat in type_stats[:10]:  # Top 10 types
            pct = (stat['count'] / summary['total_publications'] * 100) if summary['total_publications'] > 0 else 0
            print(f"  {stat['type']:<30} {stat['count']:>6} ({pct:.1f}%)")
        
        # 4. Top institutions
        logger.info("\nTOP 15 INSTITUTIONS (RECENT YEARS)")
        logger.info("-" * 70)
        inst_stats = publications_per_institution_per_year(mongo.db, start_year=2020)
        
        # Group by institution and sum
        inst_summary = {}
        for stat in inst_stats:
            inst_name = stat['institution']
            if inst_name not in inst_summary:
                inst_summary[inst_name] = 0
            inst_summary[inst_name] += stat['count']
        
        # Sort and display top 15
        top_institutions = sorted(inst_summary.items(), key=lambda x: x[1], reverse=True)[:15]
        for rank, (inst_name, count) in enumerate(top_institutions, 1):
            print(f"  {rank:>2}. {inst_name:<40} {count:>5} publications")
        
        # 5. Top authors
        logger.info("\nTOP 15 AUTHORS (BY PUBLICATION COUNT)")
        logger.info("-" * 70)
        author_stats = top_authors(mongo.db, limit=15)
        
        for rank, author in enumerate(author_stats, 1):
            print(f"  {rank:>2}. {author['orcid_id']} ({author['count']:>3} publications)")
        
        # 6. Top contributors (including co-authors)
        logger.info("\nTOP 15 CONTRIBUTORS (CO-AUTHORS INCLUDED)")
        logger.info("-" * 70)
        contributor_stats = author_contributor_analysis(mongo.db, limit=15)
        
        for rank, contrib in enumerate(contributor_stats, 1):
            name = contrib.get('name', 'Unknown')[:40]
            print(f"  {rank:>2}. {name:<40} {contrib['publication_count']:>3} publications")
        
        # 7. Recent trends (last 5 years)
        logger.info("\nRECENT TRENDS (LAST 5 YEARS)")
        logger.info("-" * 70)
        recent_summary = publication_metrics_summary(mongo.db, start_year=2020)
        recent_yearly = publications_per_year(mongo.db, start_year=2020)
        
        print(f"  Recent Total Publications: {recent_summary['total_publications']:,}")
        print(f"  Recent Avg Authors/Pub: {recent_summary['avg_authors_per_publication']}")
        print("\n  Year-by-Year Breakdown:")
        for stat in recent_yearly:
            pct_change = "->"
            if len(recent_yearly) > 1:
                idx = recent_yearly.index(stat)
                if idx > 0:
                    prev_count = recent_yearly[idx-1]['count']
                    if stat['count'] > prev_count:
                        pct_change = "UP"
                    elif stat['count'] < prev_count:
                        pct_change = "DOWN"
            print(f"    {stat['year']}: {stat['count']:>6} {pct_change}")
        
        # Compile report dictionary
        report = {
            "summary": summary,
            "publications_per_year": yearly_stats,
            "publications_per_type": type_stats,
            "publications_per_institution": inst_stats,
            "top_authors": author_stats,
            "top_contributors": contributor_stats,
            "generation_timestamp": summary['computed_at']
        }
        
        # Save report if requested
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"\nSUCCESS: Report saved to: {output_path.absolute()}")
        
        logger.info("\n" + "=" * 70)
        logger.info("SUCCESS: ANALYSIS COMPLETE")
        logger.info("=" * 70)
        
        return report
    
    except Exception as e:
        logger.error(f"\nERROR: Generating report: {str(e)}")
        raise
    
    finally:
        if mongo:
            mongo.close()


def main():
    """Main entry point."""
    # Load environment
    load_dotenv()
    
    mongo_uri = os.getenv("MONGO_CONN")
    db_name = os.getenv("DB_NAME")
    
    if not mongo_uri or not db_name:
        logger.error("Missing MONGO_CONN or DB_NAME environment variables")
        logger.error("Configure your .env file with:")
        logger.error("  MONGO_CONN=<mongodb_uri>")
        logger.error("  DB_NAME=<database_name>")
        sys.exit(1)
    
    # Generate report
    output_file = "reports/publication_analysis.json"
    generate_analysis_report(mongo_uri, db_name, output_file)


if __name__ == "__main__":
    main()
