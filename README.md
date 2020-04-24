# CS-7650-Project
muti-word bias neutralization.

## Installation

```
Under Project folder, do the following:
$ python3 -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
$ python
>> import nltk; nltk.download("punkt")

```
You need download pretrained bert model.

1. Download the Bert pretrained model from [s3](https://s3.amazonaws.com/models.huggingface.co/bert/bert-base-uncased-pytorch_model.bin)
1.1 wget https://s3.amazonaws.com/models.huggingface.co/bert/bert-base-uncased-pytorch_model.bin
1.2 mv bert-base-uncased-pytorch_model.bin pytorch_model.bin
2. Download the Bert config file from [s3](https://s3.amazonaws.com/models.huggingface.co/bert/bert-base-uncased-config.json)
2.1 wget https://s3.amazonaws.com/models.huggingface.co/bert/bert-base-uncased-config.json
2.2 mv bert-base-uncased-config.json config.json
3. Download the Bert vocab file from [s3](https://s3.amazonaws.com/models.huggingface.co/bert/bert-base-uncased-vocab.txt)
3.1 wget https://s3.amazonaws.com/models.huggingface.co/bert/bert-base-uncased-vocab.txt
3.2 mv bert-base-uncased-vocab.txt bert_vocab.txt
4. Rename:
    - `bert-base-uncased-pytorch_model.bin` to `pytorch_model.bin`
    - `bert-base-uncased-config.json` to `config.json`
    - `bert-base-uncased-vocab.txt` to `bert_vocab.txt`
5. Place `model` ,`config` and `vocab` file into  the `./src/strongClassifier/pybert/pretrain/bert/base-uncased` directory.
6. Modify your data format according to [kaggle data](https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge/data) and place in `pybert/dataset`.
    -  you can modify the `io.task_data.py` to adapt your data.
7. Run `python run_bert.py --do_data` to preprocess data.
8. Run `python run_bert.py --do_train --save_best --do_lower_case` to fine tuning bert model.
9. Run `run_bert.py --do_test --do_lower_case` to predict new data.

You need download pretrained GLOVE embedding.

Download (http://nlp.stanford.edu/data/wordvecs/glove.6B.zip), unzip, and put glove.6B.100d.txt to ./src/seq2seq/

You need to install R software environment and its packages "mclust" and "rjson".

## How to use our code.

Please consult main.h to get a sense of how to run the code for each model. You might need to change file names during experiment.


