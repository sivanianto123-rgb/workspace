import pytest

from ragdesk.generator import ExtractiveGenerator
from ragdesk.pipeline import RagPipeline

RAFT_DOC = """
# raftsim

A small simulation of the Raft consensus algorithm. A distributed system
needs its machines to agree on the order of operations even when some of
them crash. Raft elects a single leader per term; the leader replicates a
log to its followers. An entry is committed once a majority of the cluster
has stored it, which is why a minority partition can never elect a
competing leader.
"""

VEC_DOC = """
# vecsearch

A from-scratch implementation of HNSW, the approximate nearest neighbour
algorithm used by most production vector databases. Retrieval-augmented
generation embeds a question and finds the nearest document chunks to it.
HNSW organizes vectors into layers: layer 0 holds everything, higher layers
are sparser, enabling fast greedy search.
"""


@pytest.fixture
def pipeline() -> RagPipeline:
    p = RagPipeline(generator=ExtractiveGenerator())
    p.ingest_text("raftsim", RAFT_DOC)
    p.ingest_text("vecsearch", VEC_DOC)
    return p
