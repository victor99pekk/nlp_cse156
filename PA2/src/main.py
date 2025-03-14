import torch
from torch.utils.data import DataLoader
from torch.nn.utils.rnn import pad_sequence
import os
import torch.optim as optim
import torch.nn.functional as F
import sys
import argparse
from utilities import Utilities


from transformer import Classifier, Decoder
from tokenizer import SimpleTokenizer
from dataset import SpeechesClassificationDataset, LanguageModelingDataset


seed = 42

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

""" Hyperparameters to use for training to roughly match 
the numbers mentioned in the assignment description """
batch_size = 16  # Number of independent sequences  we will process in parallel
block_size = 32  # Maximum context length for predictions
learning_rate = 1e-3  # Learning rate for the optimizer
n_embd = 64  # Embedding dimension
n_head = 2  # Number of attention heads
n_layer = 4  # Number of transformer layers


eval_interval = 100  # How often to evaluate train and test perplexity during training
max_iters = 500 # For language modeling, we can process all the batches for the entire dataset, but that takes a while, so we'll limit it to 500 iterations. For batch size of 16 and block size of  32, this is roughly, this is  500 * 16 * 32 = 256000 tokens, SOTA LMs are trained on trillions of tokens, so this is a very small dataset.
eval_iters = 200  # Number of iterations to evaluate perplexity on the test set


## classifier training hyperparameters. It is a simple 1 hidden layer feedforward network, with input 
## size of 64, hidden size of 50 and output size of 3.

n_input = 64  # Input size for the classifier, should match the embedding size of the transformer
n_hidden = 100  # Hidden size for the classifier
n_output = 3  # Output size for the classifier, we have 3 classes
epochs_CLS = 15 # epochs for classifier training

def load_texts(directory):
    """
    This function loads all texts from the specified directory, ignoring any files with "test" in their name. The text is used for "training" the tokenizer. Since our tokenizer is simple, we don't need to do any training, but we still need to ignore the test data. 
    """

    texts = []
    files = os.listdir(directory)
    for filename in files: 
        if "test" in filename:  ## don't "read test files"
            continue
        with open(os.path.join(directory, filename), 'r', encoding='utf-8') as file:
            texts.append(file.read())
    return texts



def collate_batch(batch):
    """ Collate a batch of data into a single tensor with padding."""
    data, labels = zip(*batch)  # Separate the data and labels
    # Pad sequences to the fixed length
    padded_sequences = pad_sequence(data, batch_first=True, padding_value=0)
    padded_sequences = padded_sequences[:, :block_size]  # Truncate if longer
    # Add padding if shorter
    padded_sequences = torch.nn.functional.pad(padded_sequences, (0, max(0, block_size - padded_sequences.shape[1])), "constant", 0)
    labels = torch.stack(labels)  
    return padded_sequences, labels

def compute_classifier_accuracy(classifier, data_loader):
    """ Compute the accuracy of the classifier on the data in data_loader."""
    classifier.eval()
    total_correct = 0
    total_samples = 0
    with torch.no_grad():
        for X, Y in data_loader:
            X, Y = X.to(device), Y.to(device)
            probs, prediction = classifier(X)
            _, predicted = torch.max(probs.data, 1)
            total_correct += (predicted == Y).sum().item()
            total_samples += Y.size(0)
        accuracy = (100 * total_correct / total_samples)
        classifier.train()
        return accuracy


def compute_perplexity(decoderLMmodel, data_loader, eval_iters=100):
    """ Compute the perplexity of the decoderLMmodel on the data in data_loader.
    Make sure to use the cross entropy loss for the decoderLMmodel.
    """
    decoderLMmodel.eval()
    losses= []
    # total_loss = 0
    for X, Y in data_loader:
        X, Y = X.to(device), Y.to(device)
        loss,_ = decoderLMmodel(X, Y) # your model should be computing the cross entropy loss
        losses.append(loss.item())
        # total_loss += loss.item()
        if len(losses) >= eval_iters: break


    losses = torch.tensor(losses)
    mean_loss = losses.mean()
    perplexity = torch.exp(mean_loss).item()  # Calculate perplexity as exp(mean loss)

    decoderLMmodel.train()
    return perplexity

def main(transformer_arch):

    print("Loading data and creating tokenizer ...")
    texts = load_texts('PA2_code/speechesdataset')
    tokenizer = SimpleTokenizer(' '.join(texts)) # create a tokenizer from the data
    print("Vocabulary size is", tokenizer.vocab_size)

    train_CLS_dataset = SpeechesClassificationDataset(tokenizer, "PA2_code/speechesdataset/train_CLS.tsv")
    train_CLS_loader = DataLoader(train_CLS_dataset, batch_size=batch_size,collate_fn=collate_batch,shuffle=True)
    
    test_CLS_dataset = SpeechesClassificationDataset(tokenizer, "PA2_code/speechesdataset/test_CLS.tsv")
    test_CLS_loader = DataLoader(test_CLS_dataset, batch_size=batch_size, collate_fn=collate_batch, shuffle=False)

     # for the classification  task, you will train for a fixed number of epochs like this:

    # utils = Utilities(tokenizer, model.encoder)
    # utils.sanity_check("hello how are you today?", 32)
    
    if transformer_arch == 'ENCODER':
        vocab_size = tokenizer.vocab_size
        model = Classifier(vocab_size).to(device)
        optimizer = optim.Adam(model.parameters(),lr=1e-3)
        loss = 0
        utils = Utilities(tokenizer, model.encoder)
        utils.sanity_check("Because I know our work has not only helped so many Americans, it has inspired so many Americans, especially so many young people out there, to believe that you can make a difference, to hitch your wagon to something bigger than yourselves.", 32)

        for epoch in range(epochs_CLS):
            for xb, target in train_CLS_loader:
                xb, target = xb.to(device), target.to(device)
                num_classes = 3
                one_hot_tensor = torch.zeros((target.size(0), num_classes), dtype=torch.float32)
                one_hot_tensor.scatter_(1, target.unsqueeze(1), 1)
                optimizer.zero_grad()
                probs, predicted = model(xb)

                loss = F.cross_entropy(probs, one_hot_tensor)
                loss.backward()
                optimizer.step()
            test_accuracy = compute_classifier_accuracy(model, test_CLS_loader)
            train_accuracy = compute_classifier_accuracy(model, train_CLS_loader)

            print(f"Epoch {epoch + 1}, Loss: {loss.item():.3f}, Train Accuracy: {train_accuracy:.3f}%, Test Accuracy: {test_accuracy:.3f}%")

        final_accuracy = compute_classifier_accuracy(model, test_CLS_loader)
        print(f"Final Test Accuracy: {final_accuracy}%")
        utils = Utilities(tokenizer, model.encoder)
        utils.sanity_check("Because I know our work has not only helped so many Americans, it has inspired so many Americans, especially so many young people out there, to believe that you can make a difference, to hitch your wagon to something bigger than yourselves.", 32)

    else:

        # for the language modeling task, you will iterate over the training data for a fixed number of iterations like this:
        inputfile = "train_LM.txt"
        train_LM_loader = get_dataLoader(tokenizer, inputfile)
        vocab_size = 5755
        model = Decoder(n_embd, vocab_size)
        optimizer = optim.Adam(model.parameters(),lr=1e-3)
        loss = 0
        print()
        utils = Utilities(tokenizer, model)
        string = "Because I know our work has not only helped so many Americans, it has inspired so many Americans"
        utils.sanity_check(string, 32)
        for i, (xb, yb) in enumerate(train_LM_loader):
            if i >= max_iters:
                break
            elif i % 100 == 0:
                print(f"perplexities after {i} iterations")
                print("training data test: " ,compute_perplexity(model, train_LM_loader))
                print("obama data test: " ,compute_perplexity(model, get_dataLoader(tokenizer, "test_LM_obama.txt")))
                print("hbush data test: " ,compute_perplexity(model, get_dataLoader(tokenizer, "test_LM_hbush.txt")))
                print("wbush data test: " ,compute_perplexity(model, get_dataLoader(tokenizer, "test_LM_wbush.txt")))
                print("----------------------\n")
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            loss, _ = model(xb, yb)
            loss.backward()
            optimizer.step()
        print("training data test: " ,compute_perplexity(model, train_LM_loader))
        print("obama data test: " ,compute_perplexity(model, get_dataLoader(tokenizer, "test_LM_obama.txt")))
        print("hbush data test: " ,compute_perplexity(model, get_dataLoader(tokenizer, "test_LM_hbush.txt")))
        print("wbush data test: " ,compute_perplexity(model, get_dataLoader(tokenizer, "test_LM_wbush.txt")))
        print("----------------------\n")

        print()
        utils = Utilities(tokenizer, model)
        string = "Because I know our work has not only helped so many Americans, it has inspired so many Americans"
        utils.sanity_check(string, 32)


def get_dataLoader(tokenizer, inputfile):
    inputfile = "PA2_code/speechesdataset/" + inputfile
    with open(inputfile, 'r', encoding='utf-8') as f:
        lmtrainText = f.read()
    train_LM_dataset = LanguageModelingDataset(tokenizer, lmtrainText,  block_size)
    train_LM_loader = DataLoader(train_LM_dataset, batch_size=batch_size, shuffle=True)
    return train_LM_loader



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Train and evaluate a language model.')
    parser.add_argument('inputfile', type=str, help='The input file for training the language model.')
    args = parser.parse_args()
    main(args.inputfile)
