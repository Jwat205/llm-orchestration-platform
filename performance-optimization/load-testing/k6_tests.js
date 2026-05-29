/**
 * K6 Load Testing Scripts for LLM Platform
 * High-performance load testing with detailed metrics
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Custom metrics
const apiResponseTime = new Trend('api_response_time');
const tokensPerSecond = new Trend('tokens_per_second');
const errorRate = new Rate('api_errors');
const completionRate = new Rate('completion_success');
const streamingLatency = new Trend('streaming_first_token_latency');
const totalRequests = new Counter('total_requests');

// Bullet 1: non-inference latency (<100ms claim)
const nonInferenceLatency = new Trend('non_inference_latency');

// Bullet 4: cache hit vs miss latency (200ms → <50ms claim)
const cacheMissLatency = new Trend('cache_miss_latency');
const cacheHitLatency = new Trend('cache_hit_latency');

// Test configuration
export const options = {
  scenarios: {
    // Baseline load test
    baseline: {
      executor: 'constant-vus',
      vus: 10,
      duration: '5m',
      gracefulRampDown: '30s',
      tags: { test_type: 'baseline' },
    },
    
    // Spike test
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 5 },
        { duration: '2m', target: 50 },
        { duration: '1m', target: 5 },
        { duration: '1m', target: 0 },
      ],
      gracefulRampDown: '30s',
      tags: { test_type: 'spike' },
    },
    
    // Stress test
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 20 },
        { duration: '5m', target: 20 },
        { duration: '2m', target: 40 },
        { duration: '5m', target: 40 },
        { duration: '2m', target: 0 },
      ],
      gracefulRampDown: '30s',
      tags: { test_type: 'stress' },
    },
    
    // Soak test
    soak: {
      executor: 'constant-vus',
      vus: 15,
      duration: '30m',
      gracefulRampDown: '1m',
      tags: { test_type: 'soak' },
    },

    // Bullet 1: non-inference latency validation (<100ms)
    non_inference: {
      executor: 'constant-vus',
      vus: 50,
      duration: '2m',
      gracefulRampDown: '10s',
      tags: { test_type: 'non_inference' },
      exec: 'nonInferenceTest',
    },

    // Bullet 4: cache performance validation (200ms → <50ms)
    cache_performance: {
      executor: 'constant-vus',
      vus: 10,
      duration: '2m',
      gracefulRampDown: '10s',
      tags: { test_type: 'cache' },
      exec: 'cachePerformanceTest',
    },
  },
  
  thresholds: {
    http_req_duration: ['p(95)<5000'],
    api_errors: ['rate<0.05'],
    completion_success: ['rate>0.95'],
    tokens_per_second: ['avg>5'],
    // Bullet 1: non-inference endpoints must stay under 100ms
    non_inference_latency: ['p(95)<100'],
    // Bullet 4: cached responses must be under 50ms
    cache_hit_latency: ['p(95)<50'],
  },
};

// Test data
const testPrompts = [
  "Write a short story about a robot learning to paint.",
  "Explain quantum computing in simple terms.",
  "Create a recipe for chocolate chip cookies.",
  "Describe the benefits of renewable energy.",
  "Write a poem about the ocean.",
  "Explain how machine learning works.",
  "List 10 tips for better productivity.",
  "Describe the history of the internet.",
  "Write a letter to a friend about your vacation.",
  "Explain the water cycle."
];

const models = ["llama-2-7b", "llama-2-13b", "mistral-7b"];

// Base URL and headers
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8001';
const API_KEY = __ENV.API_KEY || 'test_api_key_12345';

const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json',
};

/**
 * Test chat completions endpoint
 */
export function testChatCompletion() {
  const model = randomItem(models);
  const prompt = randomItem(testPrompts);
  
  const payload = {
    model: model,
    messages: [
      { role: "user", content: prompt }
    ],
    max_tokens: randomIntBetween(50, 200),
    temperature: 0.7,
  };
  
  const startTime = Date.now();
  const response = http.post(`${BASE_URL}/v1/chat/completions`, JSON.stringify(payload), {
    headers: headers,
    timeout: '60s',
  });
  
  const endTime = Date.now();
  const duration = endTime - startTime;
  
  totalRequests.add(1);
  apiResponseTime.add(duration);
  
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'has choices': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.choices && body.choices.length > 0;
      } catch {
        return false;
      }
    },
    'response time < 30s': () => duration < 30000,
  });
  
  if (success) {
    completionRate.add(1);
    
    try {
      const body = JSON.parse(response.body);
      if (body.usage && body.usage.completion_tokens) {
        const tokensGenerated = body.usage.completion_tokens;
        const tokensPerSec = tokensGenerated / (duration / 1000);
        tokensPerSecond.add(tokensPerSec);
      }
    } catch (e) {
      console.error('Error parsing response:', e);
    }
  } else {
    errorRate.add(1);
    completionRate.add(0);
    console.error(`Chat completion failed: ${response.status} - ${response.body}`);
  }
  
  return response;
}

/**
 * Test streaming chat completions
 */
export function testStreamingCompletion() {
  const model = randomItem(models);
  const prompt = randomItem(testPrompts);
  
  const payload = {
    model: model,
    messages: [
      { role: "user", content: prompt }
    ],
    max_tokens: 100,
    temperature: 0.7,
    stream: true,
  };
  
  const startTime = Date.now();
  const response = http.post(`${BASE_URL}/v1/chat/completions`, JSON.stringify(payload), {
    headers: headers,
    timeout: '60s',
  });
  
  totalRequests.add(1);
  
  const success = check(response, {
    'streaming status is 200': (r) => r.status === 200,
    'content-type is text/event-stream': (r) => 
      r.headers['Content-Type'] && r.headers['Content-Type'].includes('text/event-stream'),
  });
  
  if (success) {
    // Measure time to first token (approximated)
    const firstTokenTime = Date.now() - startTime;
    streamingLatency.add(firstTokenTime);
    
    // Count chunks in streaming response
    const chunks = response.body.split('\n').filter(line => line.startsWith('data:'));
    if (chunks.length > 0) {
      completionRate.add(1);
    } else {
      completionRate.add(0);
      errorRate.add(1);
    }
  } else {
    errorRate.add(1);
    completionRate.add(0);
    console.error(`Streaming completion failed: ${response.status}`);
  }
  
  return response;
}

/**
 * Test embeddings endpoint
 */
export function testEmbeddings() {
  const prompt = randomItem(testPrompts);
  
  const payload = {
    model: "text-embedding-ada-002",
    input: [prompt],
  };
  
  const startTime = Date.now();
  const response = http.post(`${BASE_URL}/v1/embeddings`, JSON.stringify(payload), {
    headers: headers,
    timeout: '30s',
  });
  
  const duration = Date.now() - startTime;
  
  totalRequests.add(1);
  apiResponseTime.add(duration);
  
  const success = check(response, {
    'embeddings status is 200': (r) => r.status === 200,
    'has embedding data': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data && body.data.length > 0 && body.data[0].embedding;
      } catch {
        return false;
      }
    },
  });
  
  if (success) {
    completionRate.add(1);
  } else {
    errorRate.add(1);
    completionRate.add(0);
    console.error(`Embeddings failed: ${response.status} - ${response.body}`);
  }
  
  return response;
}

/**
 * Test function calling
 */
export function testFunctionCalling() {
  const payload = {
    model: "llama-2-7b",
    messages: [
      { role: "user", content: "What's the weather like in New York?" }
    ],
    functions: [
      {
        name: "get_weather",
        description: "Get current weather for a location",
        parameters: {
          type: "object",
          properties: {
            location: {
              type: "string",
              description: "City name"
            }
          },
          required: ["location"]
        }
      }
    ],
    max_tokens: 100,
  };
  
  const startTime = Date.now();
  const response = http.post(`${BASE_URL}/v1/chat/completions`, JSON.stringify(payload), {
    headers: headers,
    timeout: '60s',
  });
  
  const duration = Date.now() - startTime;
  
  totalRequests.add(1);
  apiResponseTime.add(duration);
  
  const success = check(response, {
    'function calling status is 200': (r) => r.status === 200,
    'response has function call or content': (r) => {
      try {
        const body = JSON.parse(r.body);
        const choice = body.choices && body.choices[0];
        return choice && (choice.message.function_call || choice.message.content);
      } catch {
        return false;
      }
    },
  });
  
  if (success) {
    completionRate.add(1);
  } else {
    errorRate.add(1);
    completionRate.add(0);
  }
  
  return response;
}

/**
 * Test model listing
 */
export function testModelListing() {
  const response = http.get(`${BASE_URL}/v1/models`, {
    headers: headers,
    timeout: '10s',
  });
  
  totalRequests.add(1);
  
  const success = check(response, {
    'models status is 200': (r) => r.status === 200,
    'has model data': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data && Array.isArray(body.data);
      } catch {
        return false;
      }
    },
  });
  
  if (!success) {
    errorRate.add(1);
    console.error(`Model listing failed: ${response.status}`);
  }
  
  return response;
}

/**
 * Test health endpoint
 */
export function testHealthCheck() {
  const response = http.get(`${BASE_URL}/health`, {
    timeout: '5s',
  });
  
  check(response, {
    'health check status is 200': (r) => r.status === 200,
  });
  
  return response;
}

/**
 * Main test function
 */
export default function() {
  // Health check (10% of requests)
  if (Math.random() < 0.1) {
    testHealthCheck();
    sleep(1);
    return;
  }
  
  // Model listing (5% of requests)
  if (Math.random() < 0.05) {
    testModelListing();
    sleep(1);
    return;
  }
  
  // Random test selection based on realistic usage patterns
  const testType = Math.random();
  
  if (testType < 0.5) {
    // 50% regular chat completions
    testChatCompletion();
  } else if (testType < 0.7) {
    // 20% streaming completions
    testStreamingCompletion();
  } else if (testType < 0.9) {
    // 20% embeddings
    testEmbeddings();
  } else {
    // 10% function calling
    testFunctionCalling();
  }
  
  // Realistic user think time
  sleep(randomIntBetween(1, 5));
}

/**
 * Bullet 1: Non-inference latency test
 * Validates health, monitoring/health, and monitoring/metrics stay under 100ms.
 */
export function nonInferenceTest() {
  const endpoints = [
    { url: `${BASE_URL}/health`, name: 'health' },
    { url: `${BASE_URL}/api/v1/monitoring/health`, name: 'monitoring/health' },
    { url: `${BASE_URL}/api/v1/monitoring/metrics`, name: 'monitoring/metrics' },
  ];

  for (const endpoint of endpoints) {
    const start = Date.now();
    const response = http.get(endpoint.url, { headers, timeout: '5s', tags: { name: endpoint.name } });
    const duration = Date.now() - start;

    nonInferenceLatency.add(duration);
    totalRequests.add(1);

    check(response, {
      [`${endpoint.name} status 200`]: (r) => r.status === 200,
      [`${endpoint.name} under 100ms`]: () => duration < 100,
    });

    if (response.status !== 200) errorRate.add(1);
  }

  sleep(randomIntBetween(1, 3));
}

/**
 * Bullet 4: Cache performance test
 * Makes the same request twice — first is a cache miss, second is a cache hit.
 * Validates that cache hits come back under 50ms.
 */
export function cachePerformanceTest() {
  const prompt = randomItem(testPrompts);
  const model = randomItem(models);

  const payload = JSON.stringify({
    model: model,
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 50,
    temperature: 0.0, // deterministic — ensures cache key matches on repeat
  });

  const reqParams = { headers, timeout: '60s' };

  // First request — cache miss
  const missStart = Date.now();
  const missResponse = http.post(`${BASE_URL}/v1/chat/completions`, payload, reqParams);
  const missDuration = Date.now() - missStart;
  cacheMissLatency.add(missDuration);
  totalRequests.add(1);

  check(missResponse, {
    'cache miss status 200': (r) => r.status === 200,
  });

  sleep(0.1);

  // Second identical request — should be served from Redis cache
  const hitStart = Date.now();
  const hitResponse = http.post(`${BASE_URL}/v1/chat/completions`, payload, reqParams);
  const hitDuration = Date.now() - hitStart;
  cacheHitLatency.add(hitDuration);
  totalRequests.add(1);

  check(hitResponse, {
    'cache hit status 200': (r) => r.status === 200,
    'cache hit under 50ms': () => hitDuration < 50,
  });

  if (hitResponse.status !== 200) errorRate.add(1);

  sleep(randomIntBetween(1, 3));
}

/**
 * Setup function
 */
export function setup() {
  console.log('Starting LLM Platform load test...');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Test scenarios: ${Object.keys(options.scenarios).join(', ')}`);
  
  // Test connectivity
  const healthResponse = http.get(`${BASE_URL}/health`);
  if (healthResponse.status !== 200) {
    console.error(`Health check failed: ${healthResponse.status}`);
    console.error('Make sure the LLM Platform is running and accessible');
  } else {
    console.log('✓ Health check passed');
  }
  
  return { baseUrl: BASE_URL };
}

/**
 * Teardown function
 */
export function teardown(data) {
  console.log('Load test completed');
  console.log('Check the K6 summary for detailed results');
}

// Scenario-specific test functions
export function baselineTest() {
  // Lighter load for baseline
  if (Math.random() < 0.8) {
    testChatCompletion();
  } else {
    testEmbeddings();
  }
  sleep(randomIntBetween(2, 8));
}

export function spikeTest() {
  // More aggressive testing for spikes
  if (Math.random() < 0.6) {
    testChatCompletion();
  } else if (Math.random() < 0.8) {
    testStreamingCompletion();
  } else {
    testEmbeddings();
  }
  sleep(randomIntBetween(0.5, 2));
}

export function stressTest() {
  // Heavy load for stress testing
  const testType = Math.random();
  if (testType < 0.4) {
    testChatCompletion();
  } else if (testType < 0.6) {
    testStreamingCompletion();
  } else if (testType < 0.8) {
    testEmbeddings();
  } else {
    testFunctionCalling();
  }
  sleep(randomIntBetween(0.1, 1));
}

export function soakTest() {
  // Sustained load for soak testing
  if (Math.random() < 0.7) {
    testChatCompletion();
  } else {
    testEmbeddings();
  }
  sleep(randomIntBetween(3, 10));
}