"""Blast-radius computation.

The blast radius of a node is the set of downstream nodes it can influence via
directed causal edges. It answers "if this node is the culprit, how much of the
observed incident does it explain?". A larger radius makes a node a more
