import chromadb
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

client = chromadb.PersistentClient(path="../store/chroma_db")
collection = client.get_collection("essay_archive")

results = collection.get(include=["embeddings", "metadatas"])
embeddings = results["embeddings"]
titles = [m["canonical_title"] for m in results["metadatas"]]

# reduce 384 dimensions down to 2 for plotting
coords = PCA(n_components=2).fit_transform(embeddings)

unique_titles = list(set(titles))
colors = plt.cm.tab20(range(len(unique_titles)))

plt.figure(figsize=(10, 7))
for i, title in enumerate(unique_titles):
    idx = [j for j, t in enumerate(titles) if t == title]
    plt.scatter(coords[idx, 0], coords[idx, 1], color=colors[i], s=30, alpha=0.7)

plt.axis("off")
plt.tight_layout()
plt.savefig("header_image.png", dpi=200, transparent=True)
