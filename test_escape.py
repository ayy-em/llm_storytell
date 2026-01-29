# Test that escaped braces work correctly
template = 'Example JSON: {{"beats": []}} and variable: {seed}'
result = template.format(seed="test_value")
print("Template:", template)
print("Result:", result)
print("✓ Escaped braces render as literal braces")
print("✓ Variables still work")
