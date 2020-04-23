#!/usr/bin/env python
# coding: utf-8

# In[3]:


from io import open
import unicodedata
import string
import re
import random

import torch
import torch.nn as nn
from torch import optim
import torch.nn.functional as F

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# In[4]:


SOS_token = 0
EOS_token = 1


class Lang:
    def __init__(self, name):
        self.name = name
        self.word2index = {}
        self.word2count = {}
        self.index2word = {0: "SOS", 1: "EOS"}
        self.n_words = 2  # Count SOS and EOS

    def addSentence(self, sentence):
        for word in sentence.split(' '):
            self.addWord(word)

    def addWord(self, word):
        if word not in self.word2index:
            self.word2index[word] = self.n_words
            self.word2count[word] = 1
            self.index2word[self.n_words] = word
            self.n_words += 1
        else:
            self.word2count[word] += 1


# In[5]:


# Turn a Unicode string to plain ASCII, thanks to
# https://stackoverflow.com/a/518232/2809427
def unicodeToAscii(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

# Lowercase, trim, and remove non-letter characters


def normalizeString(s):
    s = unicodeToAscii(s.lower().strip())
    s = re.sub(r"([.!?])", r" \1", s)
    s = re.sub(r"[^a-zA-Z.!?]+", r" ", s)
    return s


# In[6]:


def readLangs(lang1, lang2, reverse=False):
    print("Reading lines...")

    # Read the file and split into lines
    lines = open('./src/dataPreprocess/%s-%s.pair.train' % (lang1, lang2), encoding='utf-8').        read().strip().split('\n')
    print('len(lines)',len(lines))
    n_train = len(lines)
    lines_test = open('./src/dataPreprocess/%s-%s.pair.test' % (lang1, lang2), encoding='utf-8').        read().strip().split('\n')
    print('len(lines_test)',len(lines_test))
    lines_clustering = open('./src/clustering/%s-%s.space.only' % (lang1, lang2), encoding='utf-8').        read().strip().split('\n')
    print('len(lines_clustering)',len(lines_clustering))
    # Split every line into pairs and normalize
#     pairs = [[normalizeString(s) for s in l.split('\t')] for l in lines]
    pairs = []
    for l in lines:
        pairs.append([normalizeString(s) for s in l.split('\t')[:2]])
    print('len(pairs)',len(pairs))
    for l in lines_test:
        pairs.append([normalizeString(s) for s in l.split('\t')[:2]])
    print('len(pairs) after append',len(pairs))

    pairs_clustering = []
    for l in lines_clustering:
        pairs_clustering.append([normalizeString(s) for s in l.split('\t')[:2]])

#     print(pairs)
    # random.shuffle(pairs)

    # Reverse pairs, make Lang instances
    if reverse:
        pairs = [list(reversed(p)) for p in pairs]
        input_lang = Lang(lang2)
        output_lang = Lang(lang1)
    else:
        input_lang = Lang(lang1)
        output_lang = Lang(lang2)
    
    # # split test/training
    # pairs_test = pairs[int(0.8*len(pairs)):]
    # pairs = pairs[:int(0.8*len(pairs))]
    # return input_lang, output_lang, pairs, pairs_test
    return input_lang, output_lang, pairs, n_train, pairs_clustering 


# In[7]:


MAX_LENGTH = 100

def filterPair(p):
    return len(p[0].split(' ')) < MAX_LENGTH and         len(p[1].split(' ')) < MAX_LENGTH

def filterPairs(pairs):
    return [pair for pair in pairs if filterPair(pair)]


# In[29]:


def prepareData(lang1, lang2, reverse=False):
    # input_lang, output_lang, pairs, pairs_test = readLangs(lang1, lang2, reverse)
    input_lang, output_lang, pairs, n_train, pairs_clustering = readLangs(lang1, lang2, reverse)
    print("Read %s sentence pairs" % len(pairs))
    # pairs = filterPairs(pairs)
    # print("Trimmed to %s sentence pairs" % len(pairs))
    print("Counting words...")
    for pair in pairs:
        input_lang.addSentence(pair[0])
        output_lang.addSentence(pair[1])
    for pair in pairs_clustering:
        input_lang.addSentence(pair[0])
    print("Counted words:")
    print(input_lang.name, input_lang.n_words)
    print(output_lang.name, output_lang.n_words)

    # pairs_test = pairs[int(0.9*len(pairs)):]
    # pairs = pairs[:int(0.9*len(pairs))]  
    pairs_test = pairs[n_train:len(pairs)]
    pairs = pairs[:n_train]
    print('len(pairs)',len(pairs))
    print('len(pairs_test)',len(pairs_test))
    print('len(pairs_clustering)',len(pairs_clustering))
    return input_lang, output_lang, pairs, pairs_test, pairs_clustering


input_lang, output_lang, pairs, pairs_test,  pairs_clustering = prepareData('bias', 'unbias', reverse=False)
print(random.choice(pairs))


# In[9]:


class AttnDecoderRNN(nn.Module):
    def __init__(self, hidden_size, output_size, dropout_p=0.1, max_length=MAX_LENGTH):
        super(AttnDecoderRNN, self).__init__()
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.dropout_p = dropout_p
        self.max_length = max_length

        self.embedding = nn.Embedding(self.output_size, self.hidden_size)
        self.attn = nn.Linear(self.hidden_size * 2, self.max_length)
        self.attn_combine = nn.Linear(self.hidden_size * 2, self.hidden_size)
        self.dropout = nn.Dropout(self.dropout_p)
        self.gru = nn.GRU(self.hidden_size, self.hidden_size)
        self.out = nn.Linear(self.hidden_size, self.output_size)

    def forward(self, input, hidden, encoder_outputs):
        embedded = self.embedding(input).view(1, 1, -1)
        embedded = self.dropout(embedded)

        attn_weights = F.softmax(
            self.attn(torch.cat((embedded[0], hidden[0]), 1)), dim=1)
        attn_applied = torch.bmm(attn_weights.unsqueeze(0),
                                 encoder_outputs.unsqueeze(0))

        output = torch.cat((embedded[0], attn_applied[0]), 1)
        output = self.attn_combine(output).unsqueeze(0)

        output = F.relu(output)
        output, hidden = self.gru(output, hidden)

        output = F.log_softmax(self.out(output[0]), dim=1)
        return output, hidden, attn_weights

    def initHidden(self):
        return torch.zeros(1, 1, self.hidden_size, device=device)


# In[10]:


def indexesFromSentence(lang, sentence):
    return [lang.word2index[word] for word in sentence.split(' ')]


def tensorFromSentence(lang, sentence):
    indexes = indexesFromSentence(lang, sentence)
    indexes.append(EOS_token)
    return torch.tensor(indexes, dtype=torch.long, device=device).view(-1, 1)


def tensorsFromPair(pair):
    input_tensor = tensorFromSentence(input_lang, pair[0])
    target_tensor = tensorFromSentence(output_lang, pair[1])
    return (input_tensor, target_tensor)


# In[11]:


teacher_forcing_ratio = 0


def train(input_tensor, target_tensor, encoder, decoder, encoder_optimizer, decoder_optimizer, criterion, max_length=MAX_LENGTH):
    encoder_hidden = encoder.initHidden()

    encoder_optimizer.zero_grad()
    decoder_optimizer.zero_grad()

    input_length = input_tensor.size(0)
    target_length = target_tensor.size(0)

    encoder_outputs = torch.zeros(max_length, encoder.hidden_size, device=device)

    loss = 0

    for ei in range(input_length):
        encoder_output, encoder_hidden = encoder(
            input_tensor[ei], encoder_hidden)
        encoder_outputs[ei] = encoder_output[0, 0]

    decoder_input = torch.tensor([[SOS_token]], device=device)

    decoder_hidden = encoder_hidden

    use_teacher_forcing = True if random.random() < teacher_forcing_ratio else False

    if use_teacher_forcing:
        # Teacher forcing: Feed the target as the next input
        for di in range(target_length):
            decoder_output, decoder_hidden, decoder_attention = decoder(
                decoder_input, decoder_hidden, encoder_outputs)
            loss += criterion(decoder_output, target_tensor[di])
            decoder_input = target_tensor[di]  # Teacher forcing

    else:
        # Without teacher forcing: use its own predictions as the next input
        for di in range(target_length):
            decoder_output, decoder_hidden, decoder_attention = decoder(
                decoder_input, decoder_hidden, encoder_outputs)
            topv, topi = decoder_output.topk(1)
            decoder_input = topi.squeeze().detach()  # detach from history as input

            loss += criterion(decoder_output, target_tensor[di])
            if decoder_input.item() == EOS_token:
                break

    loss.backward()

    encoder_optimizer.step()
    decoder_optimizer.step()

    return loss.item() / target_length


# In[12]:


import time
import math


def asMinutes(s):
    m = math.floor(s / 60)
    s -= m * 60
    return '%dm %ds' % (m, s)


def timeSince(since, percent):
    now = time.time()
    s = now - since
    es = s / (percent)
    rs = es - s
    return '%s (- %s)' % (asMinutes(s), asMinutes(rs))


# In[24]:


def trainIters(encoder, decoder, n_iters, print_every=1000, plot_every=100, learning_rate=0.01):
    start = time.time()
    plot_losses = []
    print_loss_total = 0  # Reset every print_every
    plot_loss_total = 0  # Reset every plot_every

    encoder_optimizer = optim.SGD(encoder.parameters(), lr=learning_rate)
    decoder_optimizer = optim.SGD(decoder.parameters(), lr=learning_rate)
    training_pairs = [tensorsFromPair(random.choice(pairs))
                      for i in range(n_iters)]
    criterion = nn.NLLLoss()

    for iter in range(1, n_iters + 1):
        training_pair = training_pairs[iter - 1]
        input_tensor = training_pair[0]
        target_tensor = training_pair[1]

        loss = train(input_tensor, target_tensor, encoder,
                     decoder, encoder_optimizer, decoder_optimizer, criterion)
        print_loss_total += loss
        plot_loss_total += loss

        if iter % print_every == 0:
            print_loss_avg = print_loss_total / print_every
            print_loss_total = 0
            print('%s (%d %d%%) %.4f' % (timeSince(start, iter / n_iters),
                                         iter, iter / n_iters * 100, print_loss_avg))
            evaluateRandomly(encoder, decoder, n=5)
    evaluateAllwriteToFile(encoder, decoder)
    evaluateAllwriteToFileClustering(encoder, decoder)
#             print('eval: ',evaluateRandomlyStats(encoder, decoder, n=1000))
    


# In[25]:


def evaluateAllwriteToFile(encoder, decoder):
    print("Write output sentences to file ...")
    with open('./src/seq2seq/translated_sentences.txt','w') as f:
        text = ''
        for pair in pairs_test:
            output_words, attentions = evaluate(encoder, decoder, pair[0])
            output_sentence = ' '.join(output_words)
            text+=output_sentence+'\n'
        f.write(text)

def evaluateAllwriteToFileClustering(encoder, decoder):
    print("Write output sentences to file ...")
    with open('./src/seq2seq/translated_sentences_clustering.txt','w') as f:
        text = ''
        for pair in pairs_clustering:
            output_words, attentions = evaluate(encoder, decoder, pair[0])
            output_sentence = ' '.join(output_words)
            text+=output_sentence+'\n'
        f.write(text)


# In[26]:


def evaluateRandomlyStats(encoder, decoder, n=10):
    n_correct = 0
    for i in range(n):    
        # pair = random.choice(pairs_test)
        pair = pairs_test[i]
        # pair = random.choice(pairs)
        # print('>', pair[0])
        # print('=', pair[1])
        output_words, attentions = evaluate(encoder, decoder, pair[0])
        output_sentence = ' '.join(output_words)
        # print('<', output_sentence)
        if pair[1] in output_sentence:
          n_correct+=1
          # print('correct')
        # print('')
    return 1.*n_correct/n


# In[27]:


# prepare glove 1
print("Reading GLOVE embedding...")
import numpy as np
words = []
word2idx = {}
vectors = []

glove_size = 100
with open(f'./src/seq2seq/glove.6B.{glove_size}d.txt', 'rb') as f:
    for idx,l in enumerate(f):
        line = l.decode().split()
        word = line[0]
        words.append(word)
        word2idx[word] = idx
        vectors.append(np.array(line[1:]).astype(np.float))
glove = {w: vectors[word2idx[w]] for w in words}


# In[16]:


# prepare glove embedding 2

vocab_size = input_lang.n_words
weight_matrix = np.zeros((vocab_size, glove_size))

words_found = 0
for i, word in enumerate(input_lang.word2count.keys()):
  
  try:
    weight_matrix[i] = glove[word]
    words_found += 1
  except KeyError as e:
    # print('Key Error', e)
    weight_matrix[i] = np.random.normal(scale=0.6, size=(glove_size, ))

print("vocab_size", vocab_size)
print("words found",words_found)
weights = torch.from_numpy(weight_matrix)
print('weight_matrix size',weights.size())


# In[17]:


class EncoderRNN(nn.Module):
    def __init__(self, input_size, hidden_size):
        super(EncoderRNN, self).__init__()
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(input_size, hidden_size)
        self.gru = nn.GRU(hidden_size, hidden_size)

    def forward(self, input, hidden):
        embedded = self.embedding(input).view(1, 1, -1)
        output = embedded
        output, hidden = self.gru(output, hidden)
        return output, hidden

    def initHidden(self):
        return torch.zeros(1, 1, self.hidden_size, device=device)


# In[18]:


class EncoderRNN_Glove(nn.Module):
    def __init__(self, input_size, hidden_size, weights):
        super(EncoderRNN_Glove, self).__init__()
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(input_size, hidden_size)
        # self.embedding.load_state_dict({'weight':weight_matrix})
        self.embedding.weights = nn.Parameter(weights,requires_grad=False)
        self.gru = nn.GRU(hidden_size, hidden_size)

    def forward(self, input, hidden):
        embedded = self.embedding(input).view(1, 1, -1)
        output = embedded
        output, hidden = self.gru(output, hidden)
        return output, hidden

    def initHidden(self):
        return torch.zeros(1, 1, self.hidden_size, device=device)


# In[19]:


def evaluate(encoder, decoder, sentence, max_length=MAX_LENGTH):
    with torch.no_grad():
        input_tensor = tensorFromSentence(input_lang, sentence)
        input_length = input_tensor.size()[0]
        encoder_hidden = encoder.initHidden()

        encoder_outputs = torch.zeros(max_length, encoder.hidden_size, device=device)

        for ei in range(input_length):
            encoder_output, encoder_hidden = encoder(input_tensor[ei],
                                                     encoder_hidden)
            encoder_outputs[ei] += encoder_output[0, 0]

        decoder_input = torch.tensor([[SOS_token]], device=device)  # SOS

        decoder_hidden = encoder_hidden

        decoded_words = []
        decoder_attentions = torch.zeros(max_length, max_length)

        for di in range(max_length):
            decoder_output, decoder_hidden, decoder_attention = decoder(
                decoder_input, decoder_hidden, encoder_outputs)
            decoder_attentions[di] = decoder_attention.data
            topv, topi = decoder_output.data.topk(1)
            if topi.item() == EOS_token:
                decoded_words.append('<EOS>')
                break
            else:
                decoded_words.append(output_lang.index2word[topi.item()])

            decoder_input = topi.squeeze().detach()

        return decoded_words, decoder_attentions[:di + 1]


# In[20]:


def evaluateRandomly(encoder, decoder, n=10):
    for i in range(n):
        pair = random.choice(pairs_test)
        print('>', pair[0])
        print('=', pair[1])
        output_words, attentions = evaluate(encoder, decoder, pair[0])
        output_sentence = ' '.join(output_words)
        print('<', output_sentence)
        print('')


# In[30]:


# hidden_size = 256
# encoder1 = EncoderRNN(input_lang.n_words, hidden_size).to(device)
hidden_size = glove_size
encoder1 = EncoderRNN_Glove(input_lang.n_words, hidden_size, weights).to(device)
attn_decoder1 = AttnDecoderRNN(hidden_size, output_lang.n_words, dropout_p=0.1).to(device)

trainIters(encoder1, attn_decoder1, 1000, print_every=1000,learning_rate=0.03)


# In[ ]:




