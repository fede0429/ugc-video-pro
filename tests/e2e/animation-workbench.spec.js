
const { test, expect } = require('@playwright/test');

const mockPlan = {
  story_bible: { title: '《失控合约》' },
  characters: [{ name: '沈晚' }, { name: '周叙' }],
  episode: { episode_title: 'EP01 公开亮相失控' },
  consistency_report: { score: 91 },
  continuity_report: { ok: true },
  shot_templates: [{ template_id: 'reveal_closeup' }],
  consistency_profiles: {},
  character_states: { 沈晚: ['guarded', 'angry'] },
  scene_assets: { reusable_assets: [{ asset_id: 'asset_1' }] },
  scene_state_flow: { transitions: [{ from: 'scene_1', to: 'scene_2' }] },
  episode_asset_reuse: { inherited_assets: ['penthouse'] },
  relationship_graph: { nodes: 2, edges: 1, strongest_pair: '沈晚-周叙' },
  story_memory_bank: { open_loops: ['直播事故'] },
  outline_editor: { scenes: [{ scene_id: 'scene_1' }] },
  season_memory_bank: { season_id: 's1', open_loops: ['幕后黑手'] },
  dialogue_styles: { 沈晚: { tone: '冷静' } },
  season_conflict_tree: { core_conflict: '伪装关系崩盘' },
  scene_pacing: { total_recommended_seconds: 65, pace: 'fast burn' },
  climax_plan: { main_climax_scene: 'scene_4' },
  emotion_arcs: { 沈晚: { dominant_arc: '压抑转爆发' } },
  punchline_dialogue: { lines: [{ scene_id: 'scene_4', punchline: '你以为你赢了？' }] },
  scene_twists: { strongest_twist: 'scene_3' },
  highlight_shots: { hero_highlight: 'shot_7' },
  shot_emotion_filters: { dominant_filter: 'high contrast suspense' },
  foreshadow_plan: { seeds: [{ scene_id: 'scene_2', seed_type: 'line' }] },
  payoff_tracker: { main_payoff_scene: 'scene_4' },
  suspense_keeper: { suspense_index: 72.5, strongest_hold_scene: 'scene_3' },
  payoff_strength: { overall_strength: 70.5, best_payoff: 'scene_4' },
  season_suspense_chain: { strongest_chain: '身份曝光' },
  finale_payoff_plan: { hero_payoff: '直播事故反转' },
  season_trailer_generator: { hero_line: '一切都只是开始。' },
  next_season_hook_planner: { hook: '真正的幕后黑手现身' },
  trailer_editor: { hero_cut: ['scene_4', 'scene_5'] },
  next_episode_cold_open: { opening_image: '血色宴会厅' },
  render_meta: { provider: 'kie.ai', model: 'seedance_2', dry_run: true },
};

const mockTask = {
  task_id: 'task_demo_001',
  status: 'completed',
  stage: 'completed',
  stage_message: 'dry-run completed',
  progress: 100,
  output_video: '/api/animation/tasks/task_demo_001/artifact/output_video',
  subtitle_path: '/api/animation/tasks/task_demo_001/artifact/subtitle',
  storyboard_path: '/api/animation/tasks/task_demo_001/artifact/storyboard',
  task_dir: '/tmp/task_demo_001',
  error: null,
  artifacts: {
    output_video: '/api/animation/tasks/task_demo_001/artifact/output_video',
    subtitle: '/api/animation/tasks/task_demo_001/artifact/subtitle',
    storyboard: '/api/animation/tasks/task_demo_001/artifact/storyboard',
    plan: '/api/animation/tasks/task_demo_001/artifact/plan',
  },
  plan: mockPlan,
  shot_results: [{ shot_id: 'shot_1', status: 'completed' }],
  batch_parent_id: 'batch_001',
  batch_children: ['task_demo_002'],
};

function mockJsonFor(url, method) {
  if (url.includes('/api/animation/health')) return { status: 'ok' };
  if (url.includes('/api/animation/projects/plan')) return mockPlan;
  if (url.includes('/api/animation/projects/consistency-check')) {
    return {
      consistency_report: mockPlan.consistency_report,
      continuity_report: mockPlan.continuity_report,
      episode_title: mockPlan.episode.episode_title,
      shot_templates: mockPlan.shot_templates,
      relationship_graph: mockPlan.relationship_graph,
      story_memory_bank: mockPlan.story_memory_bank,
      dialogue_styles: mockPlan.dialogue_styles,
      season_conflict_tree: mockPlan.season_conflict_tree,
      scene_pacing: mockPlan.scene_pacing,
      climax_plan: mockPlan.climax_plan,
      shot_emotion_filters: mockPlan.shot_emotion_filters,
      foreshadow_plan: mockPlan.foreshadow_plan,
      payoff_tracker: mockPlan.payoff_tracker,
      suspense_keeper: mockPlan.suspense_keeper,
      payoff_strength: mockPlan.payoff_strength,
    };
  }
  if (url.includes('/api/animation/projects/scene-pacing')) return { scene_pacing: mockPlan.scene_pacing, episode_title: mockPlan.episode.episode_title };
  if (url.includes('/api/animation/projects/climax-plan')) return { climax_plan: mockPlan.climax_plan, episode_title: mockPlan.episode.episode_title };
  if (url.includes('/api/animation/projects/render-batch')) return { batch_task_id: 'batch_001', task_ids: ['task_demo_001', 'task_demo_002'], status: 'processing' };
  if (url.includes('/api/animation/projects/render')) return { task_id: 'task_demo_001', status: 'processing', stage: 'queued', stage_message: 'queued', task_dir: '/tmp/task_demo_001' };
  if (url.includes('/api/animation/tasks/task_demo_001') && !url.includes('/artifact/')) return mockTask;
  if (url.endsWith('/api/animation/tasks') || url.includes('/api/animation/tasks?')) return { tasks: [mockTask] };
  if (url.includes('/api/animation/templates')) return { templates: [{ template_id: 'reveal_closeup' }] };
  if (url.includes('/api/animation/states')) return { states: mockPlan.character_states };
  if (url.includes('/api/animation/scene-assets')) return mockPlan.scene_assets;
  if (url.includes('/api/animation/scene-flow')) return mockPlan.scene_state_flow;
  if (url.includes('/api/animation/batch-assets/')) return { batch_id: 'batch_001', reusable_assets: ['penthouse'] };
  if (url.includes('/api/animation/relationship-graph')) return mockPlan.relationship_graph;
  if (url.includes('/api/animation/memory/')) return mockPlan.story_memory_bank;
  if (url.includes('/api/animation/outline-editor')) return mockPlan.outline_editor;
  if (url.includes('/api/animation/season-memory')) return mockPlan.season_memory_bank;
  if (url.includes('/api/animation/emotion-arcs')) return mockPlan.emotion_arcs;
  if (url.includes('/api/animation/punchline-dialogue')) return mockPlan.punchline_dialogue;
  if (url.includes('/api/animation/scene-twists')) return mockPlan.scene_twists;
  if (url.includes('/api/animation/highlight-shots')) return mockPlan.highlight_shots;
  if (url.includes('/api/animation/shot-emotion-filters')) return mockPlan.shot_emotion_filters;
  if (url.includes('/api/animation/foreshadow-plan')) return mockPlan.foreshadow_plan;
  if (url.includes('/api/animation/payoff-tracker')) return mockPlan.payoff_tracker;
  if (url.includes('/api/animation/suspense-keeper')) return mockPlan.suspense_keeper;
  if (url.includes('/api/animation/payoff-strength')) return mockPlan.payoff_strength;
  if (url.includes('/api/animation/season-suspense-chain')) return mockPlan.season_suspense_chain;
  if (url.includes('/api/animation/finale-payoff-plan')) return mockPlan.finale_payoff_plan;
  if (url.includes('/api/animation/season-trailer-generator')) return mockPlan.season_trailer_generator;
  if (url.includes('/api/animation/next-season-hook-planner')) return mockPlan.next_season_hook_planner;
  if (url.includes('/api/animation/trailer-editor')) return mockPlan.trailer_editor;
  if (url.includes('/api/animation/next-episode-cold-open')) return mockPlan.next_episode_cold_open;
  if (url.includes('/api/animation/reference/upload')) return { asset_id: 'asset_ref_001', url: '/api/animation/assets/asset_ref_001' };
  if (url.includes('/api/animation/assets/')) return null;
  if (url.includes('/api/animation/shots/retry')) return mockTask;
  return { ok: true, method, url };
}

async function installMocks(page) {
  if (process.env.ANIMATION_E2E_MOCK === '0') return;
  await page.route('**/api/animation/**', async route => {
    const req = route.request();
    const url = req.url();
    if (url.includes('/api/animation/assets/') || url.includes('/artifact/')) {
      await route.fulfill({ status: 200, body: 'binary-mock', contentType: 'text/plain' });
      return;
    }
    const body = mockJsonFor(url, req.method());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
}

async function seedPage(page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'demo-token');
    localStorage.setItem('ugcvp_access_token', 'demo-token');
    localStorage.setItem('animation_active_task_id', 'task_demo_001');
  });
  await page.goto('/animation-studio.html');
  await expect(page.locator('h1')).toContainText('动画剧创作 Studio');
  await page.locator('#title').fill('《失控合约》');
  await page.locator('#episode-goal').fill('伪装关系第一次公开亮相，却因为旧情人出现而失控');
  await page.locator('#goal').fill('直播事故反转并引出幕后黑手');
  await page.locator('#batch-goals').fill('第一集：亮相失控\n第二集：旧情人来袭');
}

const previewButtons = [
  { button: '#btn-emotion-arcs', preview: '#emotion-arcs-preview', text: '压抑转爆发' },
  { button: '#btn-punchlines', preview: '#punchline-preview', text: '你以为你赢了？' },
  { button: '#btn-scene-twists', preview: '#scene-twists-preview', text: 'scene_3' },
  { button: '#btn-highlight-shots', preview: '#highlight-shots-preview', text: 'shot_7' },
  { button: '#btn-suspense-keeper', preview: '#suspense-keeper-preview', text: '72.5' },
  { button: '#btn-payoff-strength', preview: '#payoff-strength-preview', text: '70.5' },
  { button: '#btn-load-state-machine', preview: '#state-box', text: 'guarded' },
  { button: '#btn-load-scene-assets', preview: '#asset-box', text: 'asset_1' },
  { button: '#btn-load-scene-flow', preview: '#scene-flow-output', text: 'scene_2' },
  { button: '#btn-load-relationship-graph', preview: '#relationship-preview', text: 'strongest_pair' },
  { button: '#btn-scene-pacing', preview: '#pacing-preview', text: '65' },
  { button: '#btn-climax-plan', preview: '#climax-preview', text: 'scene_4' },
  { button: '#btn-shot-emotion-filters', preview: '#shot-emotion-filters-preview', text: 'high contrast suspense' },
  { button: '#btn-foreshadow-plan', preview: '#foreshadow-preview', text: 'seed_type' },
  { button: '#btn-payoff-tracker', preview: '#payoff-tracker-preview', text: 'scene_4' },
  { button: '#btn-dialogue-style', preview: '#dialogue-style-preview', text: '冷静' },
  { button: '#btn-season-conflict', preview: '#season-conflict-preview', text: '伪装关系崩盘' },
  { button: '#btn-outline', preview: '#outline-preview', text: 'scene_1' },
  { button: '#btn-season-memory', preview: '#season-memory-preview', text: '幕后黑手' },
  { button: '#season-suspense-chain-btn', preview: '#season-suspense-chain-preview', text: '身份曝光' },
  { button: '#finale-payoff-plan-btn', preview: '#finale-payoff-plan-preview', text: '直播事故反转' },
  { button: '#season-trailer-generator-btn', preview: '#season-trailer-generator-preview', text: '一切都只是开始。' },
  { button: '#next-season-hook-planner-btn', preview: '#next-season-hook-planner-preview', text: '幕后黑手现身' },
  { button: '#trailer-editor-btn', preview: '#trailer-editor-preview', text: 'hero_cut' },
  { button: '#next-episode-cold-open-btn', preview: '#next-episode-cold-open-preview', text: '血色宴会厅' },
];

test.describe('Animation Studio workbench', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page);
    await seedPage(page);
  });

  test('covers all preview and planning buttons', async ({ page }) => {
    await page.locator('#plan-btn').click();
    await expect(page.locator('#plan-preview')).toContainText('EP01');
    await expect(page.locator('#form-status')).toContainText(/规划|完成|成功/);

    await page.locator('#check-consistency-btn').click();
    await expect(page.locator('#consistency-preview')).toContainText('91');

    await page.locator('#load-templates-btn').click();
    await expect(page.locator('#template-preview')).toContainText('reveal_closeup');

    for (const item of previewButtons) {
      await page.locator(item.button).click();
      await expect(page.locator(item.preview)).toContainText(item.text);
    }
  });

  test('covers task actions: render, batch, refresh and retry', async ({ page }) => {
    await page.locator('#render-btn').click();
    await expect(page.locator('#task-status')).toContainText('task_demo_001');
    await expect(page.locator('#task-id')).toHaveValue('task_demo_001');
    await expect(page.locator('#task-links')).toContainText('output_video');

    await page.locator('#batch-render-btn').click();
    await expect(page.locator('#task-status')).toContainText(/batch_001|task_demo_001/);

    await page.locator('#refresh-btn').click();
    await expect(page.locator('#task-list')).toContainText('task_demo_001');

    await page.locator('#retry-task-id').fill('task_demo_001');
    await page.locator('#retry-shot-id').fill('shot_1');
    await page.locator('#retry-shot-btn').click();
    await expect(page.locator('#task-status')).toContainText('shot_1');
  });
});
