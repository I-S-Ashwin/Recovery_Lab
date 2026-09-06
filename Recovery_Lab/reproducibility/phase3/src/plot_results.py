"""Static development-only diagnostic figure, using exported tuning predictions."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


def plot(root):
    d=pd.read_json(root/'data/operational_tuning_predictions.jsonl',lines=True)
    trials=json.loads((root/'reports/trials.json').read_text())
    summary=json.loads((root/'reports/summary.json').read_text())
    imp=json.loads((root/'reports/global_feature_importance.json').read_text())[:6]
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    fig.suptitle('TVS Credit — CatBoost development results',fontsize=19,fontweight='bold')
    fig.supxlabel('Operational tuning only • 576 observed sales • Final test remains reserved',fontsize=11,color='#555555')
    blue='#2455A4';orange='#D57727';grey='#7B8490'
    money=FuncFormatter(lambda v,p:f'{v/1000:.0f}k')
    ax=axes[0,0]
    ax.scatter(d.actual_sale,d.ordered_q50,s=15,alpha=.5,color=blue,rasterized=True)
    lim=max(d.actual_sale.max(),d.ordered_q50.max())*1.05
    ax.plot([0,lim],[0,lim],color=grey,linestyle='--',linewidth=1)
    ax.set(xlim=(0,lim),ylim=(0,lim),xlabel='Actual sale (INR)',ylabel='Predicted median (INR)',title='Predictions against observed sale values')
    ax.xaxis.set_major_formatter(money);ax.yaxis.set_major_formatter(money)
    ax=axes[0,1]
    vals=[summary['comparison'][0]['baseline']['mae_inr'],summary['comparison'][0]['catboost']['mae_inr']]
    bars=ax.bar(['Baseline','Selected CatBoost'],vals,color=[grey,blue],width=.55)
    ax.bar_label(bars,labels=[f'INR {x:,.0f}' for x in vals],padding=5)
    ax.set_ylim(0,max(vals)*1.2);ax.set(title='Average absolute error',ylabel='MAE (INR)')
    ax=axes[1,0]
    bars=ax.bar([r['trial_id'] for r in trials],[r['mae_inr'] for r in trials],color=[blue if r['trial_id']==summary['winner'] else '#AAB9CF' for r in trials])
    ax.set(title='Six predeclared configurations',ylabel='Operational tuning MAE (INR)')
    ax.set_ylim(0,max(r['mae_inr'] for r in trials)*1.15)
    ax.bar_label(bars,labels=[f'{r["mae_inr"]:,.0f}' for r in trials],padding=4,fontsize=9)
    ax=axes[1,1]
    labels={'asset_cost_at_disbursal':'Original asset cost','months_since_agreement_at_seizure':'Time since agreement',
            'customer_region':'Region','customer_branch':'Branch','customer_state':'State','asset_variant':'Variant',
            'asset_model':'Model','asset_fuel_type':'Fuel type','pincode_tier':'Settlement tier'}
    ax.barh([labels.get(x['feature'],x['feature']) for x in imp][::-1],[x['importance'] for x in imp][::-1],color=blue)
    ax.set(title='Global feature importance',xlabel='PredictionValuesChange importance')
    for ax in axes.flat:
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.savefig(root/'reports/Development_Results.png',dpi=150,facecolor='white')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    plot(p.parse_args().output)
