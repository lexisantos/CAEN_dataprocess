from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import pandas as pd

def ajuste_lineal(x, y):
    model = LinearRegression()
    X_df = pd.DataFrame(x.T)

    model.fit(X_df, y)

    y_pred = model.predict(X_df)

    return {
        'coef': model.coef_[0],
        'y0': model.intercept_,
        'R2': r2_score(y, y_pred)
    }