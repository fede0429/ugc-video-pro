
const { test, expect } = require('@playwright/test');

const isMock = process.env.ANIMATION_E2E_MOCK !== '0';

const ugcButtons = [
  { id: 'btn-generate', expectNetwork: '/api/video/generate/ugc' },
  { id: 'btn-logout' },
];

const animationButtons = [
  { id: 'btn-emotion-arcs', box: '#emotion-arcs-preview', expectNetwork: '/api/animation/emotion-arcs' },
  { id: 'btn-punchlines', box: '#punchline-preview', expectNetwork: '/api/animation/punchline-dialogue' },
  { id: 'btn-scene-twists', box: '#scene-twists-preview', expectNetwork: '/api/animation/scene-twists' },
  { id: 'btn-highlight-shots', box: '#highlight-shots-preview', expectNetwork: '/api/animation/highlight-shots' },
  { id: 'btn-suspense-keeper', box: '#suspense-keeper-preview', expectNetwork: '/api/animation/suspense-keeper' },
  { id: 'btn-payoff-strength', box: '#payoff-strength-preview', expectNetwork: '/api/animation/payoff-strength' },
  { id: 'btn-load-state-machine', box: '#state-box', expectNetwork: '/api/animation/states' },
  { id: 'btn-load-scene-assets', box: '#asset-box', expectNetwork: '/api/animation/scene-assets' },
  { id: 'btn-load-scene-flow', box: '#scene-flow-output', expectNetwork: '/api/animation/scene-flow' },
  { id: 'btn-load-relationship-graph', box: '#relationship-preview', expectNetwork: '/api/animation/relationship-graph' },
  { id: 'btn-scene-pacing', box: '#pacing-preview', expectNetwork: '/api/animation/projects/scene-pacing' },
  { id: 'btn-climax-plan', box: '#climax-preview', expectNetwork: '/api/animation/projects/climax-plan' },
  { id: 'btn-shot-emotion-filters', box: '#shot-emotion-filters-preview', expectNetwork: '/api/animation/shot-emotion-filters' },
  { id: 'btn-foreshadow-plan', box: '#foreshadow-preview', expectNetwork: '/api/animation/foreshadow-plan' },
  { id: 'btn-payoff-tracker', box: '#payoff-tracker-preview', expectNetwork: '/api/animation/payoff-tracker' },
  { id: 'check-consistency-btn', box: '#consistency-output', expectNetwork: '/api/animation/projects/consistency-check' },
  { id: 'load-templates-btn', box: '#templates-output', expectNetwork: '/api/animation/templates' },
  { id: 'plan-btn', box: '#plan-output', expectNetwork: '/api/animation/projects/plan' },
  { id: 'btn-outline-editor', box: '#outline-preview', expectNetwork: '/api/animation/outline-editor' },
  { id: 'btn-season-memory', box: '#season-memory-preview', expectNetwork: '/api/animation/season-memory/' },
  { id: 'btn-dialogue-styles', box: '#dialogue-styles-preview', expectNetwork: '/api/animation/dialogue-styles' },
  { id: 'btn-season-conflict', box: '#season-conflict-preview', expectNetwork: '/api/animation/season-conflict/' },
  { id: 'btn-season-suspense-chain', box: '#season-suspense-chain-preview', expectNetwork: '/api/animation/season-suspense-chain' },
  { id: 'btn-finale-payoff-plan', box: '#finale-payoff-preview', expectNetwork: '/api/animation/finale-payoff-plan' },
  { id: 'btn-season-trailer-generator', box: '#season-trailer-preview', expectNetwork: '/api/animation/season-trailer-generator' },
  { id: 'btn-next-season-hook-planner', box: '#next-season-hook-preview', expectNetwork: '/api/animation/next-season-hook-planner' },
  { id: 'btn-trailer-editor', box: '#trailer-editor-preview', expectNetwork: '/api/animation/trailer-editor' },
  { id: 'btn-next-episode-cold-open', box: '#cold-open-preview', expectNetwork: '/api/animation/next-episode-cold-open' },
  { id: 'render-btn', box: '#render-output', expectNetwork: '/api/animation/projects/render' },
  { id: 'batch-render-btn', box: '#batch-output', expectNetwork: '/api/animation/projects/render-batch' },
  { id: 'refresh-tasks-btn', box: '#tasks-output', expectNetwork: '/api/animation/tasks' },
  { id: 'retry-shot-btn', box: '#retry-shot-output', expectNetwork: '/api/animation/shots/retry' },
];

function installMockRoutes(page) {
  const json = (payload) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  page.route('**/api/video/generate/ugc', async (route) => {
    await route.fulfill(json({ task_id: 'ugc_task_mock_1', status: 'queued' }));
  });
  page.route('**/api/video/**', async (route) => {
    await route.fulfill(json({ ok: true }));
  });
  page.route('**/api/animation/health', async (route) => {
    await route.fulfill(json({ status: 'ok' }));
  });
  page.route('**/api/animation/templates', async (route) => {
    await route.fulfill(json({ templates: [{ template_id: 'reveal_closeup' }] }));
  });
  page.route('**/api/animation/tasks', async (route) => {
    await route.fulfill(json({ items: [{ task_id: 'anim_task_1', status: 'done' }] }));
  });
  page.route('**/api/animation/season-memory/**', async (route) => {
    await route.fulfill(json({ season_id: 's1', open_loops: ['hook'] }));
  });
  page.route('**/api/animation/season-conflict/**', async (route) => {
    await route.fulfill(json({ season_id: 's1', core_conflict: 'trust vs revenge' }));
  });
  page.route('**/api/animation/**', async (route) => {
    const url = route.request().url();
    await route.fulfill(json({
      ok: true,
      endpoint: url,
      preview: true,
      task_id: 'anim_task_1',
      status: 'queued',
      score: 88,
      items: [{ id: 'x1' }],
      strongest_twist: 'scene_3',
      hero_highlight: 'shot_7'
    }));
  });
}

async function fillAnimationForm(page) {
  await page.locator('#title').fill('失控合约');
  await page.locator('#core-premise').fill('豪门契约关系失控');
  await page.locator('#episode-goal').fill('建立关系、埋下反转');
  const charJson = `[{"name":"沈晚","role":"女主","traits":["冷静","克制"]},{"name":"周叙","role":"男主","traits":["强势","防御"]}]`;
  await page.locator('#characters-json').fill(charJson);
}

async function fillUGCForm(page) {
  await page.evaluate(() => {
    localStorage.setItem('token', 'mock-token');
    localStorage.setItem('ugcvp_access_token', 'mock-token');
  });
  await page.locator('#productName').fill('胶原蛋白面膜');
  await page.locator('#productDescription').fill('主打补水修护');
  await page.locator('#targetAudience').fill('25-35女性');
  await page.locator('#platform').selectOption('tiktok');
}

test.describe('studio unified e2e matrix', () => {
  test.beforeEach(async ({ page }) => {
    if (isMock) {
      await installMockRoutes(page);
    }
  });

  test('ugc dashboard matrix', async ({ page }) => {
    await page.goto('/static/index.html');
    await fillUGCForm(page);
    for (const item of ugcButtons) {
      const locator = page.locator(`#${item.id}`);
      await expect(locator).toBeVisible();
      if (item.id === 'btn-generate') {
        await locator.click();
      }
    }
  });

  test('animation workbench matrix', async ({ page }) => {
    await page.goto('/static/animation-studio.html');
    await fillAnimationForm(page);
    for (const item of animationButtons) {
      const locator = page.locator(`#${item.id}`);
      await expect(locator).toBeVisible();
      await locator.click();
      if (item.box) {
        await expect(page.locator(item.box)).toBeVisible();
      }
    }
  });
});
