import pandas as pd

df = pd.read_csv("smardgrid_iot_security.csv")

#devide normal, attack, fault
df_normal = df[df["label"] == 0]
df_attack = df[df["label"] == 1]
df_fault = df[df["label"] == 2]

#SPLIT DATA PER LABEL

normal_train = df_normal.sample(frac=0.8, random_state=42)
normal_test = df_normal.drop(normal_train.index)

attack_train = df_attack.sample(frac=0.8, random_state=42)
attack_test = df_attack.drop(attack_train.index)

fault_train = df_fault.sample(frac=0.8, random_state=42)
fault_test = df_fault.drop(fault_train.index)

#concatenate train and test data

train_df = pd.concat([normal_train, attack_train, fault_train])
test_df = pd.concat([normal_test, attack_test, fault_test])



# 1. Cek missing values per kolom
print("Missing values per kolom:")
print(df.isnull().sum())

# 2. Cek tipe data per kolom
print("\nData types per kolom:")
print(df.dtypes)

# 3. Cek duplikat baris
print(f"\nJumlah baris duplikat: {df.duplicated().sum()}")

