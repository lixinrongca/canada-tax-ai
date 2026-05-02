# import json

# def run_tests(registry, prompt_name, version=None):
#     with open(f"tests/{prompt_name}.json") as f:
#         cases = json.load(f)

#     success = 0

#     for c in cases:
#         output = run_prompt(registry, prompt_name, c["input"], version)
#         _, ok = validate_output(output)

#         if ok:
#             success += 1

#     return success / len(cases)

# def safe_run(registry, name, input_text, retries=2):
#     for i in range(retries):
#         output = run_prompt(registry, name, input_text)

#         data, ok = validate_output(output)
#         if ok:
#             return data

#     return None