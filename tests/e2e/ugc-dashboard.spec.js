
const { test, expect } = require('@playwright/test');

const mockTasks = {
  items: [
    {
      id: 'ugc_task_001',
      status: 'completed',
      created_at: '2026-03-07T10:00:00Z',
      qa_report_json: {
        score: 88,
        publish_preparation: {
          title: '这个真的救了我',
          hashtags: ['#种草', '#好物推荐']
        }
      }
    }
  ]
};

const mockTimeline = {
  task_id: 'ugc_task_001',
  status: 'completed',
  timeline: [
    { id: 'seg_1', track_type: 'a_roll', spoken_line: '我一开始真的以为这是智商税。', duration_seconds: 3.2, status: 'done' },
    { id: 'seg_2', track_type: 'b_roll', spoken_line: '', visual_prompt: 'close-up product detail', duration_seconds: 2.8, status: 'done' }
  ],
  progress: 100,
  output_video: '/api/video/download/ugc_task_001',
};

function jsonFor(url, method) {
  if (url.includes('/api/auth/login')) return { access_token: 'demo-token', refresh_token: 'refresh-demo' };
  if (url.includes('/api/auth/register')) return { access_token: 'demo-token', refresh_token: 'refresh-demo' };
  if (url.includes('/api/video/presets')) return { ok: true };
  if (url.includes('/api/video/generate/ugc')) return { task_id: 'ugc_task_001' };
  if (url.includes('/api/video/tasks?page=')) return mockTasks;
  if (url.includes('/api/video/tasks/ugc_task_001/timeline')) return mockTimeline;
  return { ok: true };
}

async function installMocks(page) {
  await page.addInitScript(() => {
    class MockWS {
      constructor(url) {
        this.url = url;
        this.readyState = 1;
        this.listeners = {};
        setTimeout(() => this._emit('open', {}), 5);
        setTimeout(() => this._emit('message', { data: JSON.stringify({
          stage: 'planning_script',
          message: '脚本已生成',
          progress: 45,
          task_id: 'ugc_task_001',
        })}), 30);
        setTimeout(() => this._emit('message', { data: JSON.stringify({
          stage: 'completed',
          message: '已完成',
          progress: 100,
          task_id: 'ugc_task_001',
          timeline: [
            { id: 'seg_1', track_type: 'a_roll', spoken_line: '我一开始真的以为这是智商税。', duration_seconds: 3.2, status: 'done' },
            { id: 'seg_2', track_type: 'b_roll', spoken_line: '', visual_prompt: 'close-up product detail', duration_seconds: 2.8, status: 'done' }
          ]
        })}), 80);
      }
      addEventListener(name, cb) {
        this.listeners[name] = this.listeners[name] || [];
        this.listeners[name].push(cb);
      }
      close() { this.readyState = 3; }
      send() {}
      _emit(name, payload) {
        (this.listeners[name] || []).forEach(cb => cb(payload));
      }
    }
    window.WebSocket = MockWS;
  });

  await page.route('**/api/**', async route => {
    const req = route.request();
    const url = req.url();
    if (url.includes('/api/video/download/')) {
      await route.fulfill({ status: 200, body: 'binary-video-mock', contentType: 'text/plain' });
      return;
    }
    const body = jsonFor(url, req.method());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
}

test.describe('UGC dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page);
  });

  test('login and submit ugc generation flow', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#auth-screen')).toBeVisible();
    await page.locator('#login-email').fill('demo@example.com');
    await page.locator('#login-pass').fill('demo-pass');
    await page.locator('#login-form button[type="submit"]').click();

    await expect(page.locator('#main-screen')).toBeVisible();

    const fileInput = page.locator('#product-grid input[type="file"]').first();
    await fileInput.setInputFiles({
      name: 'product.png',
      mimeType: 'image/png',
      buffer: Buffer.from('mock-image-data'),
    });

    await page.locator('#product-desc').fill('一款适合短视频带货的示范产品');
    await page.locator('#brand-name').fill('Demo Brand');
    await page.locator('#selling-points').fill('见效快、好上手、外观高级');
    await page.locator('#target-audience').fill('18-35女性');

    await page.locator('#btn-generate').click();

    await expect(page.locator('#stage-message')).toContainText(/脚本已生成|已完成/);
    await expect(page.locator('#task-list')).toContainText('ugc_task_001');

    // timeline may update from websocket or fallback fetch
    await expect(page.locator('#timeline-preview')).toContainText(/close-up product detail|智商税/);
  });
});
