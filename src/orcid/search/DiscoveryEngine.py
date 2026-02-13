"""
Docstring for models.DiscoveryEngine
Orchestrator class for searching and partitioning. It breaks ORCID searches into
safe, manageable chunks by recursively subpartitioning queries that exceed the 10,000
result API limit.
Responsibilities:
1) Decides what and when to search
2) Breaks problem into safe chunks
3) coordinates search and query partitioning
"""

from collections import deque
from typing import Iterable, Set
from .OrcidSearchClient import OrcidSearchClient
from .QueryPartition import QueryPartition
from ..storage.PartitionStorage import PartitionStorage
from ..storage.OrcidStorage import OrcidStorage


class DiscoveryEngine:
    def __init__(
        self,
        client: OrcidSearchClient,
        orcid_storage: OrcidStorage,
        partition_storage: PartitionStorage
    ):
        self.client = client
        self.orcid_storage = orcid_storage
        self.partition_storage = partition_storage

    """
    Function to initialize top-level partitions (A-Z) into the queue.
    base query + prefix, |prefix| = 1
    """
    def seed(self, base_query: str):
        for c in "abcdefghijklmnopqrstuvwxyz":
            self.partition_storage.add_partition(
                QueryPartition(base_query, c)
            )

    """
    Function to process partitions from the queue.
    BFS queue approach. Every oversized partition is recursively
    split into smaller ones until all partitions fit within the API limit.
    Time Complexity: O(N + P), N = total ORCID results and P = total numbers of partitions.
    If results are evenly distributed (size of results with family-name A* is the same as B*, C*, ...),
    min partions needed are N/10^4. If N is in the millions, worst case is 10^6 operations which
    is computable in 1s.
    In the absolute worst case, each recursive partition returns 10^4 results, which signals 
    exponetial growth for the depth (see QueryPartition.py)
    Space Complexity: O(P + N)
    """
    def run(self):
        while True:
            doc = self.partition_storage.fetch_next_pending() # get next partition
            if not doc: # if empty, then finished
                print("No more partitions to process.")
                break

            partition = QueryPartition.from_mongo(doc)
            print(f"Processing partition: {partition.prefix}")
            print(f"Query: {partition.to_query_string()}")

            count = self.client.estimate_count(partition) # estimate the result size of the partition
            if count == 0: # if 0 results, then continue to next object
                self.partition_storage.mark_done(doc)
                continue

            if count > 10_000: # if estimate count is more than the allowed 10^4 results, then subdivide
                for sub in partition.split():
                    self.partition_storage.add_partition(sub)
                self.partition_storage.mark_done(doc)
                continue
            
            # If count is less than or equal to 10^4, then retrieve all ORCID profiles
            profiles = self.client.fetch_orcids(partition)
            # Save discovered orcids and their related details to DB
            self.orcid_storage.save_orcids(profiles)
            self.partition_storage.mark_done(doc)
