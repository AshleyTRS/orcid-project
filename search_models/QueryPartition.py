"""
Docstring for models.QueryPartition
Helper class in the search process.
Since API limits 10,000 results per query (even when there could be more results),
it is optimal to create partitions of that search query based on the alphabet and family-name
"""

from dataclasses import dataclass
from typing import List

@dataclass # For classes meant to store data
class QueryPartition:
    base_query: str # fixed part of a query
    prefix: str # starting characters to match family name's (Alphabet based)
    depth: int = 1 # recursion depth = number of partitions applied to query

    """
    This function returns the complete query string (base_query + prefix).
    Example: "current-institution-affiliation-name:X AND family-name:Ad*"
    """
    def to_query_string(self) -> str:
        return f'{self.base_query} AND family-name:{self.prefix}*'

    """
    Recursive function to subdivide searches.
    Example: creates prefix A, Ab, Abc, Abcd, ...., Z, Za, Zab, ....
    """
    def split(self) -> List["QueryPartition"]:
        return [
            QueryPartition(
                base_query=self.base_query,
                prefix=self.prefix + chr(c),
                depth=self.depth + 1
            )
            for c in range(ord('a'), ord('z') + 1)
        ]

    @staticmethod
    def from_mongo(doc):
        return QueryPartition(
            base_query=doc["base_query"],
            prefix=doc["prefix"],
            depth=doc["depth"]
        )