import subprocess
import os

dir_path = os.path.dirname(os.path.realpath(__file__))
num_iterations = 100  # 원하는 횟수를 지정하세요.

for i in range(num_iterations):
    print(f"Running iteration {i+1} out of {num_iterations}")
    subprocess.call(["python", os.path.join(dir_path, "Main_Added_kospi.py")])

subprocess.call(["python", os.path.join(dir_path, "Result_to_excel.py")])
