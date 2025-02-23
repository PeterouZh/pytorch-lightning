<p align="center">
  <a href="https://williamfalcon.github.io/pytorch-lightning/">
    <img alt="" src="https://github.com/williamFalcon/pytorch-lightning/blob/master/docs/source/_static/lightning_logo.png" width="50">
  </a>
</p>
<h3 align="center">
  Pytorch Lightning
</h3>
<p align="center">
  The Keras for ML researchers using PyTorch. More control. Less boilerplate.    
</p>
<p align="center">
  <a href="https://badge.fury.io/py/pytorch-lightning"><img src="https://badge.fury.io/py/pytorch-lightning.svg" alt="PyPI version" height="18"></a>
  <a href="https://github.com/williamFalcon/pytorch-lightning/tree/master/tests"><img src="https://github.com/williamFalcon/pytorch-lightning/blob/master/coverage.svg"></a>
  <a href="https://travis-ci.org/williamFalcon/pytorch-lightning"><img src="https://travis-ci.org/williamFalcon/pytorch-lightning.svg?branch=master"></a>
  <a href="https://williamfalcon.github.io/pytorch-lightning/"><img src="https://readthedocs.org/projects/pytorch-lightning/badge/?version=latest"></a>
  <a href="https://github.com/williamFalcon/pytorch-lightning/blob/master/COPYING"><img src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
</p>   

```bash
pip install pytorch-lightning  
```

## Docs   
**[View the docs here](https://williamfalcon.github.io/pytorch-lightning/)**

## What is it?  
Keras and fast.ai are too abstract for researchers. Lightning abstracts the full training loop but gives you control in the critical points.   


## Why do I want to use lightning?
Because you don't want to define a training loop, validation loop, gradient clipping, checkpointing, loading, 
gpu training, etc... every time you start a project. Let lightning handle all of that for you! Just define your 
data and what happens in the training, testing and validation loop and lightning will do the rest.

To use lightning do 2 things:  
1. [Define a Trainer](https://github.com/williamFalcon/pytorch-lightning/blob/master/examples/new_project_templates/trainer_cpu_template.py).   
2. [Define a LightningModel](https://github.com/williamFalcon/pytorch-lightning/blob/master/examples/new_project_templates/lightning_module_template.py).     

## What does lightning control for me?
Everything!    
Except for these 6 core functions which you define:    

```{.python}
# what to do in the training loop
def training_step(self, data_batch, batch_nb):

# what to do in the validation loop
def validation_step(self, data_batch, batch_nb):

# how to aggregate validation_step outputs
def validation_end(self, outputs):

# and your dataloaders
def tng_dataloader():
def val_dataloader():
def test_dataloader():
```

**Could be as complex as seq-2-seq + attention**    

```python
# define what happens for training here
def training_step(self, data_batch, batch_nb):
    x, y = data_batch
    
    # define your own forward and loss calculation
    hidden_states = self.encoder(x)
     
    # even as complex as a seq-2seq + attn model
    # (this is just a toy, non-working example to illustrate)
    start_token = '<SOS>'
    last_hidden = torch.zeros(...)
    loss = 0
    for step in range(max_seq_len):
        attn_context = self.attention_nn(hidden_states, start_token)
        pred = self.decoder(start_token, attn_context, last_hidden) 
        last_hidden = pred
        pred = self.predict_nn(pred)
        loss += self.loss(last_hidden, y[step])
        
    #toy example as well
    loss = loss / max_seq_len
    return {'loss': loss} 
```

**Or as basic as CNN image classification**      

```python
# define what happens for validation here
def validation_step(self, data_batch, batch_nb):    
    x, y = data_batch
    
    # or as basic as a CNN classification
    out = self.forward(x)
    loss = my_loss(out, y)
    return {'loss': loss} 
```

**And you also decide how to collate the output of all validation steps**    

```python
def validation_end(self, outputs):
    """
    Called at the end of validation to aggregate outputs
    :param outputs: list of individual outputs of each validation step
    :return:
    """
    val_loss_mean = 0
    val_acc_mean = 0
    for output in outputs:
        val_loss_mean += output['val_loss']
        val_acc_mean += output['val_acc']

    val_loss_mean /= len(outputs)
    val_acc_mean /= len(outputs)
    tqdm_dic = {'val_loss': val_loss_mean.item(), 'val_acc': val_acc_mean.item()}
    return tqdm_dic
```
   
## Tensorboard    
Lightning is fully integrated with tensorboard.   

<p align="center">
  <a href="https://williamfalcon.github.io/pytorch-lightning/">
    <img alt="" src="https://github.com/williamFalcon/pytorch-lightning/blob/master/docs/source/_static/tf_loss.png" width="900px">
  </a>
</p>

Lightning also adds a text column with all the hyperparameters for this experiment.      

<p align="center">
  <a href="https://williamfalcon.github.io/pytorch-lightning/">
        <img alt="" src="https://github.com/williamFalcon/pytorch-lightning/blob/master/docs/source/_static/tf_tags.png" width="900px">
  </a>
</p>

Simply note the path you set for the Experiment    
``` {.python}   
from test_tube import Experiment
from pytorch-lightning import  Trainer

exp = Experiment(save_dir='/some/path')
trainer = Trainer(experiment=exp)
...
```   

And run tensorboard from that dir   
```bash
tensorboard --logdir /some/path     
```    

## Lightning automatically automates all of the following ([each is also configurable](https://williamfalcon.github.io/pytorch-lightning/Trainer/)):

###### Checkpointing    

- [Model saving](https://williamfalcon.github.io/pytorch-lightning/Trainer/Checkpointing/#model-saving)
- [Model loading](https://williamfalcon.github.io/pytorch-lightning/LightningModule/methods/#load-from-metrics) 

###### Computing cluster (SLURM)    

- [Running grid search on a cluster](https://williamfalcon.github.io/pytorch-lightning/Trainer/SLURM%20Managed%20Cluster#running-grid-search-on-a-cluster) 
- [Walltime auto-resubmit](https://williamfalcon.github.io/pytorch-lightning/Trainer/SLURM%20Managed%20Cluster#walltime-auto-resubmit)   

###### Debugging  

- [Fast dev run](https://williamfalcon.github.io/pytorch-lightning/Trainer/debugging/#fast-dev-run)
- [Inspect gradient norms](https://williamfalcon.github.io/pytorch-lightning/Trainer/debugging/#inspect-gradient-norms)
- [Log GPU usage](https://williamfalcon.github.io/pytorch-lightning/Trainer/debugging/#Log-gpu-usage)
- [Make model overfit on subset of data](https://williamfalcon.github.io/pytorch-lightning/Trainer/debugging/#make-model-overfit-on-subset-of-data)
- [Print the parameter count by layer](https://williamfalcon.github.io/pytorch-lightning/Trainer/debugging/#print-the-parameter-count-by-layer)
- [Pring which gradients are nan](https://williamfalcon.github.io/pytorch-lightning/Trainer/debugging/#print-which-gradients-are-nan)


###### Distributed training    

- [16-bit mixed precision](https://williamfalcon.github.io/pytorch-lightning/Trainer/Distributed%20training/#16-bit-mixed-precision)
- [Multi-GPU](https://williamfalcon.github.io/pytorch-lightning/Trainer/Distributed%20training/#Multi-GPU)
- [Multi-node](https://williamfalcon.github.io/pytorch-lightning/Trainer/Distributed%20training/#Multi-node)
- [Single GPU](https://williamfalcon.github.io/pytorch-lightning/Trainer/Distributed%20training/#single-gpu)
- [Self-balancing architecture](https://williamfalcon.github.io/pytorch-lightning/Trainer/Distributed%20training/#self-balancing-architecture)


###### Experiment Logging   

- [Display metrics in progress bar](https://williamfalcon.github.io/pytorch-lightning/Trainer/Logging/#display-metrics-in-progress-bar)
- Log arbitrary metrics
- [Log metric row every k batches](https://williamfalcon.github.io/pytorch-lightning/Trainer/Logging/#log-metric-row-every-k-batches)
- [Process position](https://williamfalcon.github.io/pytorch-lightning/Trainer/Logging/#process-position)
- [Save a snapshot of all hyperparameters](https://williamfalcon.github.io/pytorch-lightning/Trainer/Logging/#save-a-snapshot-of-all-hyperparameters) 
- [Snapshot code for a training run](https://williamfalcon.github.io/pytorch-lightning/Trainer/Logging/#snapshot-code-for-a-training-run) 
- [Write logs file to csv every k batches](https://williamfalcon.github.io/pytorch-lightning/Trainer/Logging/#write-logs-file-to-csv-every-k-batches)

###### Training loop    

- [Accumulate gradients](https://williamfalcon.github.io/pytorch-lightning/Trainer/Training%20Loop/#accumulated-gradients)
- [Anneal Learning rate](https://williamfalcon.github.io/pytorch-lightning/Trainer/Training%20Loop/#anneal-learning-rate)
- [Force training for min or max epochs](https://williamfalcon.github.io/pytorch-lightning/Trainer/Training%20Loop/#force-training-for-min-or-max-epochs)
- [Force disable early stop](https://williamfalcon.github.io/pytorch-lightning/Trainer/Training%20Loop/#force-disable-early-stop)
- [Gradient Clipping](https://williamfalcon.github.io/pytorch-lightning/Trainer/Training%20Loop/#gradient-clipping)
- [Use multiple optimizers (like GANs)](https://williamfalcon.github.io/pytorch-lightning/Pytorch-Lightning/LightningModule/#configure_optimizers)
- [Set how much of the training set to check (1-100%)](https://williamfalcon.github.io/pytorch-lightning/Trainer/Training%20Loop/#set-how-much-of-the-training-set-to-check)

###### Validation loop    

- [Check validation every n epochs](https://williamfalcon.github.io/pytorch-lightning/Trainer/Validation%20loop/#check-validation-every-n-epochs)
- [Set how much of the validation set to check](https://williamfalcon.github.io/pytorch-lightning/Trainer/Validation%20loop/#set-how-much-of-the-validation-set-to-check)
- [Set how much of the test set to check](https://williamfalcon.github.io/pytorch-lightning/Trainer/Validation%20loop/#set-how-much-of-the-test-set-to-check)
- [Set validation check frequency within 1 training epoch](https://williamfalcon.github.io/pytorch-lightning/Trainer/Validation%20loop/#set-validation-check-frequency-within-1-training-epoch)
- [Set the number of validation sanity steps](https://williamfalcon.github.io/pytorch-lightning/Trainer/Validation%20loop/#set-the-number-of-validation-sanity-steps)


## Demo
```bash
# install lightning
pip install pytorch-lightning

# clone lightning for the demo
git clone https://github.com/williamFalcon/pytorch-lightning.git
cd examples/new_project_templates/

# run demo (on cpu)
python trainer_gpu_cluster_template.py
```

Without changing the model AT ALL, you can run the model on a single gpu, over multiple gpus, or over multiple nodes.
```bash
# run a grid search on two gpus
python fully_featured_trainer.py --gpus "0;1"

# run single model on multiple gpus
python fully_featured_trainer.py --gpus "0;1" --interactive
```


