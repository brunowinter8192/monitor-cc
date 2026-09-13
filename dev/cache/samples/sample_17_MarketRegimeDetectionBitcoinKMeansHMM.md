Calandra A. Haryani<sup>1,\*</sup>, Chandra<sup>2</sup>, Riswan Efendi Tarigan<sup>3,</sup>

<sup>1,3</sup>Department of Information Systems, Faculty of AI and Data Science, Universitas Pelita Harapan, Indonesia

<sup>2</sup>Department of Information Systems, Bina Nusantara University, Jakarta, Indonesia

## ABSTRACT

The rapid growth of cryptocurrency markets has created new challenges in understanding and predicting the structural dynamics of digital asset prices. Bitcoin, as the most traded blockchain-based currency, exhibits extreme volatility, nonlinear patterns, and complex regime shifts that traditional financial models cannot adequately capture. This study proposes a hybrid analytical framework that integrates K Means clustering with the Hidden Markov Model to identify and model multiple market regimes in Bitcoin time series data. The Bitcoin dataset used in this research contains minute-level records that were preprocessed to extract key indicators, namely logarithmic returns and rolling volatility, which represent the short-term dynamics of market behavior. The K Means algorithm was first employed to segment the data into three distinct clusters that correspond to bullish, bearish, and sideways regimes, followed by the application of the Hidden Markov Model to estimate probabilistic transitions between these regimes over time. The results reveal that the hybrid K Means and Hidden Markov Model approach achieves superior performance compared to a standalone model, as indicated by a higher log likelihood and a lower Bayesian Information Criterion value. The transition probability matrix shows that bullish and bearish regimes are highly persistent, while the sideways regime acts as a transitional buffer that connects both market extremes. The empirical findings confirm that Bitcoin prices evolve through persistent and probabilistically determined regimes rather than random fluctuations. The proposed framework provides a more comprehensive understanding of cryptocurrency market dynamics and offers practical value for investors, risk analysts, and policymakers in designing adaptive trading and risk management strategies within blockchain-based financial ecosystems.

Keywords Bitcoin Market Analysis, Hidden Markov Model, K Means Clustering, Regime Detection, Volatility Modelling

Submitted: 5 September 2025 Accepted: 10 October 2025 Published: 16 February 2026

Corresponding author Calandra A. Haryani, calandra.haryani@uph.edu

Additional Information and Declarations can be found on page 92

DOI: 10.47738/jdmdc.v3i1.57

Copyright 2026 Haryani, et al.,

Distributed under Creative Commons CC-BY 4.0

## INTRODUCTION

The emergence of blockchain technology has revolutionized the global financial system by introducing decentralized and transparent mechanisms for value transfer and asset management [1]. Among the wide range of blockchain-based applications, Bitcoin has become the most prominent digital currency and the foundation of the cryptocurrency ecosystem [2]. As a fully decentralized asset, Bitcoin operates without centralized oversight, and its price is determined by the interaction of millions of independent participants across global exchanges. This decentralized structure creates a market that is highly sensitive to speculative sentiment, macroeconomic changes, and technological innovations, resulting in extreme volatility and unpredictable price movements [3]. The behavior of Bitcoin prices, therefore, differs significantly from that of traditional financial assets such as equities or commodities, presenting unique challenges for modeling, forecasting, and risk assessment.

Numerous studies have attempted to explain the dynamics of cryptocurrency prices using traditional statistical and econometric approaches such as Autoregressive Integrated Moving Average models, Generalized Autoregressive Conditional Heteroskedasticity models, and Vector Autoregression frameworks [4]. While these models can capture linear dependencies and short-term volatility, they often fail to represent the nonlinear and regime-dependent behavior that dominates cryptocurrency markets. Empirical evidence has shown that Bitcoin does not follow a single stationary process but rather exhibits multiple behavioral states that alternate between phases of growth, decline, and stability. This characteristic indicates that the Bitcoin market operates under a regime-switching structure, where different statistical properties govern price behavior in distinct periods. Capturing these latent regimes is essential for understanding market sentiment, improving trading strategies, and managing portfolio risk in a highly volatile environment.

In response to these challenges, this study proposes a hybrid analytical framework that integrates K Means clustering with the Hidden Markov Model to detect and model the presence of market regimes in Bitcoin price data. The combination of clustering and probabilistic modeling allows for both structural and temporal dimensions of market behavior to be analyzed. K Means clustering provides an initial unsupervised segmentation of market conditions based on standardized features of log returns and volatility, while the Hidden Markov Model captures the probabilistic transitions among these states over time. This hybrid approach addresses the limitations of conventional time series models by incorporating both cross-sectional differentiation and sequential dependency within the same framework. By applying this model to minute-level Bitcoin data, the study aims to identify distinct market regimes, estimate their transition probabilities, and interpret their economic significance in the context of blockchain-based finance.

The contribution of this research is twofold. From a methodological perspective, the study introduces an efficient and interpretable hybrid model that enhances the ability to detect and characterize complex market regimes in nonstationary financial data. The integration of K Means clustering for initialization improves the convergence and accuracy of the Hidden Markov Model, producing more reliable estimations of transition dynamics. From a practical perspective, the findings provide insights into how regime persistence, volatility cycles, and transition probabilities can be used to design adaptive trading systems and risk management tools for cryptocurrency markets. By revealing the underlying probabilistic structure of Bitcoin price movements, this research contributes to the broader understanding of blockchain-based financial systems and their implications for digital asset stability and investor decision-making.

## Literature Review

