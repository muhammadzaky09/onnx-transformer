import torch
import torch.nn as nn

import math
from utils import clones
from layer_norm import LayerNorm

import copy

class MultiHeadedAttention(nn.Module):
    def __init__(self, h, d_model, dropout=0.1, do_quantization=True):
        "Take in model size and number of heads."
        super(MultiHeadedAttention, self).__init__()
        assert d_model % h == 0
        # We assume d_v always equals d_k
        self.d_k = d_model // h
        self.h = h
        self.linears = clones(nn.Linear(d_model, d_model), 4)
        self.attn = None
        self.dropout = nn.Dropout(p=dropout)
        self.quantize = do_quantization

    def attention(self, query, key, value, mask=None, dropout=None):
        "Compute 'Scaled Dot Product Attention'"
        d_k = query.size(-1)
        scores = torch.matmul(query, key.transpose(-2, -1)) \
                 / math.sqrt(d_k)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        p_attn = nn.functional.softmax(scores, dim = -1)
        if dropout is not None:
            p_attn = dropout(p_attn)
        if self.quantize:
            p_attn.mul_(127).round_().to(torch.int8)
            p_attn.to(torch.float32).div_(127)
        return torch.matmul(p_attn, value), p_attn


    def forward(self, query, key, value, mask=None):
        def temp(l, x):
            print("##")
            print(query)
            print("--")
            print(key)
            print("--")
            print(value)
            print("##")
            print(type(l))
            return l(x).view(nbatches, -1, self.h, self.d_k).transpose(1, 2)
        "Implements Figure 2"
        if mask is not None:
            # Same mask applied to all h heads.
            mask = mask.unsqueeze(1)
        nbatches = query.size(0)
        
        # 1) Do all the linear projections in batch from d_model => h x d_k 
        query, key, value = \
            [temp(l, x) for l, x in zip(self.linears, (query, key, value))]
        
        # 2) Apply attention on all the projected vectors in batch. 
        x, self.attn = self.attention(query, key, value, mask=mask, 
                                 dropout=self.dropout)
        
        # 3) "Concat" using a view and apply a final linear. 
        x = x.transpose(1, 2).contiguous() \
             .view(nbatches, -1, self.h * self.d_k)
        return self.linears[-1](x)
