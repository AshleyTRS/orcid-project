"""
Docstring for openalex.AbstractReconstructor
Utility for rebuilding plain-text abstracts from inverted index data.

OpenAlex returns an `abstract_inverted_index` mapping words to positions;
this static method reverses that mapping into an ordered string. Any
malformed input is handled gracefully by returning `None`.
"""
class AbstractReconstructor:
    @staticmethod
    def reconstruct(index):
        if not index or not isinstance(index, dict):
            return None

        try:
            positions = {}
            for word, pos_list in index.items():
                for pos in pos_list:
                    positions[pos] = word

            ordered = [positions[i] for i in sorted(positions.keys())]
            return " ".join(ordered)
        except Exception:
            # if the index has unexpected structure, fall back to None
            return None