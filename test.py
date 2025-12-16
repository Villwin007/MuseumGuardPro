from transformers import AutoModel
m = AutoModel.from_pretrained("bert-base-uncased")
print(m.config)
