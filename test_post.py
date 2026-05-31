import urllib.request, json

code = """#include <stdio.h>

// Direct recursion
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

// Mutual recursion loop: A -> B -> A
void functionB(int x);

void functionA(int x) {
    if (x <= 0) return;
    functionB(x - 1);
}

void functionB(int x) {
    if (x <= 0) return;
    functionA(x - 1);
}

// Normal stack-using functions
int process(int a, int b) {
    int buffer[128]; // Local array allocates stack space
    for(int i = 0; i < 128; i++) {
        buffer[i] = a + b + i;
    }
    return buffer[0] + factorial(5);
}

int main() {
    printf("Starting Stack Analyzer Demo\\n");
    int result = process(10, 20);
    functionA(5);
    return result;
}"""

data = json.dumps({'code': code, 'opt': '-O0'}).encode('utf-8')
req = urllib.request.Request('http://localhost:3000/analyze', data=data, headers={'Content-Type': 'application/json'})
try:
    print("Sending POST request to /analyze...")
    resp = urllib.request.urlopen(req)
    print("Status:", resp.status)
    print(resp.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print('HTTP ERROR', e.code)
    print(e.read().decode('utf-8'))
