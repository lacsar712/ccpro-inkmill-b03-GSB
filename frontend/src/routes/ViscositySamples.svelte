<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import type { Mill, SampleCorrection, ViscositySample } from '../lib/types';

  let rows: ViscositySample[] = [];
  let mills: Mill[] = [];
  let error = '';
  let editingId: number | null = null;

  // 更正弹层状态
  let corrSample: ViscositySample | null = null;
  let corrHistory: SampleCorrection[] = [];
  let corrViscosity = '';
  let corrReason = '';
  let corrError = '';
  let corrSaving = false;

  function nowLocal(): string {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  }

  let form = {
    millId: '',
    sampledAt: nowLocal(),
    viscosityPaS: '10',
    tempC: '',
    notes: '',
  };

  async function load() {
    error = '';
    try {
      [rows, mills] = await Promise.all([
        api<ViscositySample[]>('/viscosity-samples'),
        api<Mill[]>('/mills'),
      ]);
      if (!form.millId && mills[0]) form.millId = String(mills[0].id);
    } catch (e) {
      error = e instanceof Error ? e.message : '加载失败';
    }
  }

  onMount(load);

  function millLabel(id: number): string {
    const m = mills.find((x) => x.id === id);
    return m ? `${m.millCode} (#${m.id})` : `#${id}`;
  }

  function reset() {
    form = {
      millId: mills[0] ? String(mills[0].id) : '',
      sampledAt: nowLocal(),
      viscosityPaS: '10',
      tempC: '',
      notes: '',
    };
    editingId = null;
  }

  function toLocalInput(iso: string): string {
    const d = new Date(iso.replace(' ', 'T'));
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  }

  function edit(row: ViscositySample) {
    editingId = row.id;
    form = {
      millId: String(row.millId),
      sampledAt: toLocalInput(row.sampledAt),
      viscosityPaS: String(row.originalViscosityPaS),
      tempC: row.tempC != null ? String(row.tempC) : '',
      notes: row.notes || '',
    };
  }

  async function save() {
    error = '';
    const payload = {
      millId: Number(form.millId),
      sampledAt: form.sampledAt,
      viscosityPaS: Number(form.viscosityPaS),
      tempC: form.tempC === '' ? null : Number(form.tempC),
      notes: form.notes,
    };
    try {
      if (editingId) {
        // 编辑仅允许改研磨机/温度/备注；粘度与取样时间为原始事实，后端同样拒绝修改。
        await api(`/viscosity-samples/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      } else {
        await api('/viscosity-samples', { method: 'POST', body: JSON.stringify(payload) });
      }
      reset();
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '保存失败';
    }
  }

  async function remove(id: number) {
    if (!confirm('确认删除该粘度取样记录？其全部更正记录也会一并删除。')) return;
    try {
      await api(`/viscosity-samples/${id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '删除失败';
    }
  }

  async function openCorrections(row: ViscositySample) {
    corrError = '';
    corrSample = row;
    corrViscosity = String(row.effectiveViscosityPaS);
    corrReason = '';
    corrHistory = [];
    try {
      const detail = await api<ViscositySample>(`/viscosity-samples/${row.id}`);
      // 单条 GET 与列表必须给出相同的有效粘度口径
      if (detail.effectiveViscosityPaS !== row.effectiveViscosityPaS) {
        corrError = '有效粘度在列表与单条之间不一致，请刷新后重试';
      }
      corrHistory = detail.corrections ?? [];
    } catch (e) {
      corrError = e instanceof Error ? e.message : '更正历史加载失败';
    }
  }

  function closeCorrections() {
    corrSample = null;
    corrHistory = [];
    corrError = '';
  }

  async function submitCorrection() {
    if (!corrSample) return;
    corrError = '';
    const value = Number(corrViscosity);
    if (!Number.isFinite(value) || value <= 0) {
      corrError = '更正粘度(Pa·s)必须大于 0';
      return;
    }
    if (!corrReason.trim()) {
      corrError = '更正原因不能为空';
      return;
    }
    corrSaving = true;
    try {
      const detail = await api<ViscositySample>(
        `/viscosity-samples/${corrSample.id}/corrections`,
        {
          method: 'POST',
          body: JSON.stringify({ viscosityPaS: value, reason: corrReason.trim() }),
        },
      );
      corrHistory = detail.corrections ?? [];
      corrViscosity = String(detail.effectiveViscosityPaS);
      corrReason = '';
      await load();
      corrSample = rows.find((r) => r.id === detail.id) ?? corrSample;
    } catch (e) {
      corrError = e instanceof Error ? e.message : '更正失败';
    } finally {
      corrSaving = false;
    }
  }
</script>

<header class="page-head">
  <h1>粘度取样</h1>
  <p>记录 Pa·s 粘度（必须 &gt; 0）。数值有误请<strong>追加更正</strong>，原始测量值不可覆盖。</p>
</header>

{#if error}
  <div class="err">{error}</div>
{/if}

<section class="panel">
  <h2>{editingId ? '编辑取样（粘度与取样时间不可改）' : '新增取样'}</h2>
  <div class="fields">
    <div class="field">
      <label>研磨机
        <select bind:value={form.millId}>
          {#each mills as m}
            <option value={String(m.id)}>{m.millCode}</option>
          {/each}
        </select>
      </label>
    </div>
    <div class="field">
      <label>取样时间
        <input type="datetime-local" bind:value={form.sampledAt} disabled={!!editingId} />
      </label>
    </div>
    <div class="field">
      <label>原始粘度 Pa·s
        <input type="number" step="0.0001" min="0.0001" bind:value={form.viscosityPaS} disabled={!!editingId} />
      </label>
    </div>
    <div class="field"><label>温度 ℃<input type="number" step="0.1" bind:value={form.tempC} /></label></div>
    <div class="field full"><label>备注<textarea rows="2" bind:value={form.notes} /></label></div>
  </div>
  {#if editingId}
    <p class="muted hint">原始粘度与取样时间为测量事实，不可修改；如数值有误请使用该行的“更正/历史”。</p>
  {/if}
  <div class="actions">
    <button class="btn-primary" on:click={save}>{editingId ? '保存' : '创建'}</button>
    {#if editingId}
      <button class="btn-ghost" on:click={reset}>取消</button>
    {/if}
  </div>
</section>

<section class="panel">
  <table class="data-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>研磨机</th>
        <th>取样时间</th>
        <th>原始 Pa·s</th>
        <th>有效 Pa·s</th>
        <th>更正</th>
        <th>℃</th>
        <th>备注</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{millLabel(row.millId)}</td>
          <td>{row.sampledAt}</td>
          <td>
            {#if row.correctionCount > 0}
              <span class="muted">{row.originalViscosityPaS}</span>
            {:else}
              {row.originalViscosityPaS}
            {/if}
          </td>
          <td><strong class="effective">{row.effectiveViscosityPaS}</strong></td>
          <td>
            {#if row.correctionCount > 0}
              <span class="badge grinding">{row.correctionCount} 次</span>
            {:else}
              <span class="muted">0</span>
            {/if}
          </td>
          <td>{row.tempC ?? '—'}</td>
          <td>{row.notes || '—'}</td>
          <td class="ops">
            <button class="link-btn" on:click={() => openCorrections(row)}>更正/历史</button>
            <button class="link-btn" on:click={() => edit(row)}>编辑</button>
            <button class="link-btn danger" on:click={() => remove(row.id)}>删除</button>
          </td>
        </tr>
      {:else}
        <tr><td colspan="9">暂无数据</td></tr>
      {/each}
    </tbody>
  </table>
  <p class="muted hint">有效粘度口径：无更正时取原始值；有更正时取最新一条（按更正时间、再按 id）。</p>
</section>

{#if corrSample}
  <div class="modal-overlay">
    <button class="modal-backdrop" aria-label="关闭更正窗口" on:click={closeCorrections}></button>
    <div class="modal" role="dialog" aria-modal="true" aria-label="粘度更正">
      <h2>取样 #{corrSample.id} 的更正链</h2>
      <p class="muted">
        {millLabel(corrSample.millId)} · 取样于 {corrSample.sampledAt} ·
        原始粘度 {corrSample.originalViscosityPaS} Pa·s
      </p>

      {#if corrError}
        <div class="err">{corrError}</div>
      {/if}

      <div class="fields">
        <div class="field">
          <label>更正后粘度 Pa·s（必须 &gt; 0）
            <input type="number" step="0.0001" min="0.0001" bind:value={corrViscosity} />
          </label>
        </div>
        <div class="field full">
          <label>更正原因（必填）
            <textarea rows="2" bind:value={corrReason} placeholder="例如：复测发现读数偏高，温度补偿后修正"></textarea>
          </label>
        </div>
      </div>
      <div class="actions">
        <button class="btn-primary" disabled={corrSaving} on:click={submitCorrection}>
          {corrSaving ? '提交中…' : '追加更正'}
        </button>
        <button class="btn-ghost" on:click={closeCorrections}>关闭</button>
      </div>

      <h3>更正历史（{corrHistory.length}）</h3>
      <table class="data-table corr-table">
        <thead>
          <tr>
            <th>更正时间</th>
            <th>粘度 Pa·s</th>
            <th>原因</th>
          </tr>
        </thead>
        <tbody>
          {#each corrHistory as c, i}
            <tr class:current={i === 0}>
              <td>{c.correctedAt}{i === 0 ? '（当前有效）' : ''}</td>
              <td>{c.viscosityPaS}</td>
              <td>{c.reason}</td>
            </tr>
          {:else}
            <tr><td colspan="3" class="muted">暂无更正，当前有效粘度即原始值</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{/if}

<style>
  .hint {
    font-size: 0.8rem;
    margin: 0.6rem 0 0;
  }

  .effective {
    color: var(--vermillion-400);
  }

  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 4vh 1rem;
    overflow-y: auto;
    z-index: 40;
  }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    border: none;
    padding: 0;
    background: transparent;
    cursor: default;
  }

  .modal {
    position: relative;
    z-index: 1;
    background: var(--ink-900);
    border: 1px solid var(--line);
    padding: 1.2rem 1.3rem 1.4rem;
    width: min(680px, 100%);
  }

  .modal h2 {
    margin: 0 0 0.4rem;
    font-size: 1.05rem;
    color: var(--paper);
  }

  .modal h3 {
    margin: 1.1rem 0 0.5rem;
    font-size: 0.9rem;
    color: var(--paper);
  }

  .corr-table tr.current td {
    color: var(--vermillion-400);
  }

  .btn-primary:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
</style>
