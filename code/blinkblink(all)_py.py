# -*- coding: utf-8 -*-
"""BlinkBlink(All).py

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1W8NeD_r6viddo0OC3k07mmkQlKYYsO3F
"""

!pip install autogluon

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# url = 'https://raw.githubusercontent.com/punyanuch-h/Blink_database/refs/heads/main/20250115-blink%20summary%20-%20All.csv' # database1 - Original
# url = 'https://raw.githubusercontent.com/punyanuch-h/Blink_database/refs/heads/main/blink%20summary%20-%20LR.csv' # database1 - Add abnormal_side column
url = 'https://raw.githubusercontent.com/punyanuch-h/Blink_database/refs/heads/main/blink%20summary%20-%20updated%20All.csv' # database2 - Add 2 patients
df = pd.read_csv(url)

df

"""# Convert blink_cover to %"""

r_blink_columns = [
    "r_blink_cover_20", "r_blink_cover_30", "r_blink_cover_40",
    "r_blink_cover_50", "r_blink_cover_60", "r_blink_cover_70",
    "r_blink_cover_80", "r_blink_cover_90"
]
df[r_blink_columns] = df[r_blink_columns].div(df["r_n_blinks"], axis=0) * 100
display(df[["uuid", "r_n_blinks", "r_n_incomplete_blinks"] + r_blink_columns ].head())

l_blink_columns = [
    "l_blink_cover_20", "l_blink_cover_30", "l_blink_cover_40",
    "l_blink_cover_50", "l_blink_cover_60", "l_blink_cover_70",
    "l_blink_cover_80", "l_blink_cover_90"
]
df[l_blink_columns] = df[l_blink_columns].div(df["l_n_blinks"], axis=0) * 100
display(df[["uuid","l_n_blinks", "l_n_incomplete_blinks"] + l_blink_columns].head())

df.to_csv('df_Convert_blink_cover.csv')

"""# Clean Data"""

# Drop columns with 'dur' in their names
df = df.loc[:, ~df.columns.str.contains('dur', case=False)]
df = df.drop(columns=['revisited','patient_type'])

df['r_open_peak_vel_mean'] = (df['r_late_open_peak_vel_mean'] + df['r_early_open_peak_vel_mean']) / 2
df['l_open_peak_vel_mean'] = (df['l_late_open_peak_vel_mean'] + df['l_early_open_peak_vel_mean']) / 2

df['r_open_peak_vel_std'] = ((df['r_late_open_peak_vel_std']**2 + df['r_early_open_peak_vel_std']**2) / 2) ** 0.5
df['l_open_peak_vel_std'] = ((df['l_late_open_peak_vel_std']**2 + df['l_early_open_peak_vel_std']**2) / 2) ** 0.5

df = df.loc[:, ~df.columns.str.contains('late', case=False)]
df = df.loc[:, ~df.columns.str.contains('early', case=False)]

df.to_csv('df_open_prak_vel.csv')

"""# Dataframe FNP (ALL)

## is top 5 & raw (True True)

### Prepare Data
"""

from os import replace
# ลบข้อมูลที่ uuid ลงท้ายด้วย 'N'
df_cleaned = df[~df['uuid'].str.endswith('N')]

# สร้างคอลัมน์ใหม่เพื่อแยกหมวดหมู่ของ uuid (A, B, C, D)
df_cleaned['group'] = df_cleaned['uuid'].str[0]

df_cleaned = df_cleaned[(df_cleaned['group'] == 'A') | (df_cleaned['group'] == 'C')]

df_cleaned = df_cleaned[(df_cleaned['is_top'] == True) & (df_cleaned['is_raw'] == True)]

df_cleaned.drop(['uuid','abnormal_side'],axis=1, inplace = True)

df_cleaned[['is_top','is_raw']] = df_cleaned[['is_top','is_raw']].astype(int)
df_cleaned[['group']] = df_cleaned[['group']].replace({'C': 1, 'A': 0})
df_cleaned.head()

df_cleaned

"""###Train Model"""

from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score
from autogluon.tabular import TabularPredictor
from autogluon.common import space

# แบ่งฟีเจอร์ (X) และเลเบล (y)
X = df_cleaned.drop(columns=['group'])
y = df_cleaned['group']

# กำหนดจำนวน fold
n_splits = 5
skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

# สร้างรายการเก็บผลลัพธ์ของแต่ละ fold
cv_splits = []

# ทำ 5-Fold Cross Validation
for fold, (train_valid_idx, test_idx) in enumerate(skf.split(X, y)):
    train_valid_X, test_X = X.iloc[train_valid_idx], X.iloc[test_idx]
    train_valid_y, test_y = y.iloc[train_valid_idx], y.iloc[test_idx]

    # แบ่ง Train และ Validation จาก train_valid set
    train_idx_temp, valid_idx_temp = next(
        StratifiedKFold(n_splits=4, shuffle=True, random_state=42).split(train_valid_X, train_valid_y))

    train_df = df_cleaned.iloc[train_valid_idx[train_idx_temp]]
    valid_df = df_cleaned.iloc[train_valid_idx[valid_idx_temp]]
    test_df = df_cleaned.iloc[test_idx]

    # เก็บชุดข้อมูลของ fold นี้
    cv_splits.append({
        "fold": fold + 1,
        "train": train_df,
        "valid": valid_df,
        "test": test_df
    })

    print(f"Fold {fold + 1} -> Train: {len(train_df)}, Valid: {len(valid_df)}, Test: {len(test_df)}")

# ตั้งค่าพารามิเตอร์ของ AutoGluon
label = 'group'
metric = 'balanced_accuracy'

nn_options = {
    'num_epochs': 10,
    'learning_rate': space.Real(1e-4, 1e-2, default=5e-4, log=True),
    'activation': space.Categorical('relu', 'softrelu', 'tanh'),
    'dropout_prob': space.Real(0.0, 0.5, default=0.1),
}

gbm_options = {
    'num_boost_round': 100,
    'num_leaves': space.Int(lower=26, upper=66, default=36),
}

rf_options = {
    'n_estimators': space.Int(lower=50, upper=300, default=100),
    'max_features': space.Categorical('sqrt', 'log2'),
}

xt_options = rf_options

fastai_options = nn_options

cat_options = {
    'iterations': 500,
    'depth': space.Int(4, 10, default=6)
}

xgb_options = {
    'n_estimators': 100,
    'max_depth': space.Int(3, 10, default=6)
}

knn_options = {
    'n_neighbors': space.Int(3, 15, default=5)
}

lr_options = {}

hyperparameters = {
    'GBM': gbm_options,
    'NN_TORCH': nn_options,
    'RF': rf_options,
    'XT': xt_options,
    'FASTAI': fastai_options,
    'CAT': cat_options,
    'XGB': xgb_options,
    'KNN': knn_options,
    'LR': lr_options,
}

time_limit = 5 * 60
num_trials = 5
search_strategy = 'auto'

hyperparameter_tune_kwargs = {
    'num_trials': num_trials,
    'scheduler': 'local',
    'searcher': search_strategy,
}

# เก็บผลลัพธ์ของแต่ละ fold
cv_results = []
all_acc_scores = []
all_f1_scores = []
all_feature_importance = []

for fold_data in cv_splits:
    fold = fold_data["fold"]
    train_data = fold_data["train"]
    valid_data = fold_data["valid"]
    test_data = fold_data["test"]

    print(f"\nTraining AutoGluon on Fold {fold}...")

    predictor = TabularPredictor(label=label, eval_metric=metric).fit(
        train_data=train_data,
        tuning_data=valid_data,
        time_limit=time_limit,
        hyperparameters=hyperparameters,
        hyperparameter_tune_kwargs=hyperparameter_tune_kwargs,
        use_bag_holdout=True,
        presets='best_quality'
    )

    # ตรวจสอบว่าโมเดลไหนดีที่สุด (ข้อ 1)
    leaderboard = predictor.leaderboard(test_data, silent=True)
    print(f"\nLeaderboard for Fold {fold}:")
    print(leaderboard)

    # ตรวจสอบโมเดลที่ดีที่สุด (ข้อ 2)
    best_model = predictor.model_best
    print(f"Best model for Fold {fold}: {best_model}")

    # ประเมินผลบน Test set
    test_score = predictor.evaluate(test_data)
    print(f"Fold {fold} Test Score: {test_score}")

    # ทำการทำนาย
    x_test = test_data.drop(columns=[label])
    y_actual = test_data[label]
    y_pred = predictor.predict(x_test)

    # คำนวณ Accuracy และ F1 Score
    acc = accuracy_score(y_actual, y_pred)
    f1 = f1_score(y_actual, y_pred)

    print(f"Accuracy: {acc:.4f}")
    print(f"F1 Score: {f1:.4f}")

    # เก็บค่า Accuracy และ F1 Score
    all_acc_scores.append(acc)
    all_f1_scores.append(f1)

    # คำนวณ Feature Importance
    feature_importance = predictor.feature_importance(test_data)
    important_features = feature_importance[feature_importance['importance'] > 0]
    print("\nImportant Features:")
    print(important_features)
    all_feature_importance.append(important_features)

    # เก็บผลลัพธ์ของ Fold
    cv_results.append({
        "fold": fold,
        "predictor": predictor,
        "leaderboard": leaderboard,
        "best_model": best_model,
        "test_score": test_score,
        "accuracy": acc,
        "f1_score": f1,
        "feature_importance": important_features
    })

# คำนวณค่าเฉลี่ยของ Test Score, Accuracy และ F1 Score
mean_test_score = np.mean([result["test_score"]["balanced_accuracy"] for result in cv_results])
mean_acc = np.mean(all_acc_scores)
mean_f1 = np.mean(all_f1_scores)

print("\nFinal Cross-Validation Results")
print(f"Mean Balanced Accuracy: {mean_test_score:.4f}")
print(f"Mean Accuracy: {mean_acc:.4f}")
print(f"Mean F1 Score: {mean_f1:.4f}")