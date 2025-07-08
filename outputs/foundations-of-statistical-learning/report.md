# Foundations of Statistical Learning

Statistical learning involves building predictive models from data. It encompasses tasks where a function *f* is learned to map inputs (features) X to outputs Y, balancing accuracy and model complexity【^1】. Key distinctions include:
- **Supervised vs Unsupervised:** Supervised learning uses labeled examples (each input has an output); unsupervised learning uses only inputs without labels【^1】【^2】.
- **Regression vs Classification:** Regression predicts a continuous outcome, classification predicts a categorical label【^1】.
- **Parametric vs Nonparametric:** Parametric methods assume a fixed functional form for *f* with finite parameters, while nonparametric methods make fewer assumptions and can adapt complexity to the data【^2】.
- **Prediction vs Inference:** Statistical learning methods aim either to predict new data accurately or to infer underlying relationships in the data【^2】.

## Loss, Risk, and Decision Theory
Statistical decisions rely on a loss function \(\ell(y,\hat y)\) that quantifies prediction error, and *risk* defined as the expected loss under the data distribution【^3】【^4】. Learning algorithms typically minimize risk by minimizing *empirical risk* (average loss on training data). However, empirical risk underestimates true risk on new data, leading to a potential gap known as generalization error【^4】. Overfitting occurs when a model fits the training data too closely (including noise), and underfitting happens when it is too simple to capture underlying trends【^1】. 

- **Bias-Variance Tradeoff:** Complex models can achieve low bias but high variance; simpler models have high bias and low variance. Optimally trading off bias and variance is key for good generalization【^6】.
- **Regularization:** Adding penalties (e.g. L2 norm) or constraints to the loss function can limit model flexibility, controlling overfitting and improving stability【^1】.

## Model Evaluation and Selection
To assess performance, cross-validation or held-out testing is used to estimate a model’s generalization error. This guides model selection and hyperparameter tuning in a principled way【^4】. Ensemble methods (bagging, boosting) combine multiple models (e.g. decision trees) to reduce variance and often improve accuracy.

## Common Models and Methods
- **Linear Models:** Linear regression (for continuous outputs) and logistic regression (for binary classification) assume a linear relationship between inputs and output. Parameters are estimated by minimizing squared error or log-loss【^1】.
- **Decision Trees:** Tree-based models split data by feature tests and handle both regression and classification. They are simple predictive models where leaves represent outcomes【^5】.  
- **Ensembles (Bagging, Boosting):** Methods like random forests (bagging many trees) and boosting (sequentially trained models) improve accuracy by combining weak learners【^5】.
- **Instance-based (k-NN):** The k-nearest neighbors algorithm predicts an output by looking at the k closest training examples in feature space and using their labels (majority vote for classification, average for regression)【^9】.
- **Probabilistic (Naive Bayes):** Naive Bayes classifiers apply Bayes’ theorem under the (naive) assumption that features are independent given the class. They compute class probabilities for prediction【^8】.
- **Support Vector Machines:** SVMs learn a maximum-margin hyperplane that separates classes. They can also implicitly map inputs into high-dimensional spaces via kernels for nonlinear classification【^10】【^10】.
- **Neural Networks:** Deep neural networks are interconnected layers of processing units ('neurons') whose weights are learned by optimizing a loss function with methods like gradient descent【^7】.
- **Dimensionality Reduction (PCA):** Principal Component Analysis is an unsupervised method that finds orthogonal directions of maximum variance. It transforms data into a lower-dimensional space to mitigate high-dimensional challenges【^5】.

Statistical learning integrates these concepts and models to enable robust prediction and inference from data, emphasizing generalization performance on unseen data.

## Footnotes
