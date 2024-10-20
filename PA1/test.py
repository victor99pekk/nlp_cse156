

import torch
from sentiment_data import WordEmbeddings, read_word_embeddings

def func(n):
    return n+1

file='data/glove.6B.50d-relativized.txt'
wordembeddings = read_word_embeddings(file)
embedding_layer = wordembeddings.get_initialized_embedding_layer()

wordembeddings = read_word_embeddings(file)

word_index_tensor = func(torch.tensor([1], dtype=torch.long))
word_index_tensor2 = torch.tensor([2], dtype=torch.long)

word_embedding = embedding_layer(word_index_tensor)
word_embedding2 = embedding_layer(word_index_tensor2)

column_tensor = torch.arange(512).repeat(16, 1)

tensor1 = torch.tensor([1, 2], dtype=torch.float)
tensor2 = torch.tensor([2, 2])
print(torch.nn.LogSoftmax(dim=0)(tensor1))
print(embedding_layer.weight)


# print(column_tensor)

# print(wordembeddings.get_embedding('and'))


# print(word_embedding2)
# print(word_embedding)