<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import type { Mill, ViscositySample } from '../lib/types';

  let rows: ViscositySample[] = [];
  let mills: Mill[] = [];
  let error = '';
  let editingId: number | null = null;
  let correctingId: number | null = null;
  let corrBusy = false;

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

  let corrForm = { viscosityPaS: '', reason: '' };

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
    correctingId = null;
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
    if (!confirm('确认删除该粘度取样记录？其全部更正记录将一并删除。')) return;
    try {
      await api(`/viscosity-samples/${id}`, { method: 'DELETE' });
      if (correctingId === id) correctingId = null;
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '删除失败';
    }
  }

  function openCorrection(row: ViscositySample) {
    correctingId = row.id;
    editingId = null;
    corrForm = { viscosityPaS: String(row.effectiveViscosityPaS), reason: '' };
    error = '';
  }

  function correctingRow(): ViscositySample | undefined {
    return rows.find((r) => r.id === correctingId);
  }

  // 仅在 {#if correctingRow()} 块内使用,运行时必定存在。
  function correctionTarget(): ViscositySample {
    return correctingRow() as ViscositySample;
  }

  async function submitCorrection() {
    const row = correctingRow();
    if (!row) return;
    error = '';
    const value = Number(corrForm.viscosityPaS);
    if (!Number.isFinite(value) || value <= 0) {
      error = '粘度(Pa·s)必须大于 0';
      return;
    }
    if (!corrForm.reason.trim()) {
      error = '更正原因不能为空';
      return;
    }
    corrBusy = true;
    try {
      await api(`/viscosity-samples/${row.id}/corrections`, {
        method: 'POST',
        body: JSON.stringify({ viscosityPaS: value, reason: corrForm.reason.trim() }),
      });
      corrForm.reason = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '更正失败';
    } finally {
      corrBusy = false;
    }
  }
</script>

<header class="page-head">
  <h1>粘度取样</h1>
  <p>记录 Pa·s 粘度（必须 &gt; 0）。粘度一经取样不可覆盖，只能<strong>追加更正</strong>，以最新更正为有效粘度。</p>
</header>

{#if error}
  <div class="err">{error}</div>
{/if}

<section class="panel">
  <h2>{editingId ? '编辑取样（粘度不可在此修改，请用更正）' : '新增取样'}</h2>
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
    <div class="field"><label>取样时间<input type="datetime-local" bind:value={form.sampledAt} /></label></div>
    <div class="field">
      <label>粘度 Pa·s
        <input
          type="number"
          step="0.0001"
          min="0.0001"
          bind:value={form.viscosityPaS}
          disabled={!!editingId}
          title={editingId ? '原始粘度不可修改，请通过“更正”追加' : ''}
        />
      </label>
    </div>
    <div class="field"><label>温度 ℃<input type="number" step="0.1" bind:value={form.tempC} /></label></div>
    <div class="field full"><label>备注<textarea rows="2" bind:value={form.notes} /></label></div>
  </div>
  <div class="actions">
    <button class="btn-primary" on:click={save}>{editingId ? '保存' : '创建'}</button>
    {#if editingId}
      <button class="btn-ghost" on:click={reset}>取消</button>
    {/if}
  </div>
</section>

{#if correctingRow()}
  {@const target = correctionTarget()}
  <section class="panel corr-panel">
    <h2>追加更正 · 取样 #{target.id}（{millLabel(target.millId)}）</h2>
    <p class="muted">
      原始粘度 {target.originalViscosityPaS} Pa·s，当前有效粘度
      <strong class="eff">{target.effectiveViscosityPaS}</strong> Pa·s，
      已有 {target.correctionCount} 条更正。提交后以最新更正为有效粘度。
    </p>
    <div class="fields">
      <div class="field">
        <label>更正后粘度 Pa·s
          <input type="number" step="0.0001" min="0.0001" bind:value={corrForm.viscosityPaS} />
        </label>
      </div>
      <div class="field full">
        <label>更正原因（必填）<textarea rows="2" bind:value={corrForm.reason} placeholder="例如：复测发现读数偏差 / 温度补偿" /></label>
      </div>
    </div>
    <div class="actions">
      <button class="btn-primary" disabled={corrBusy} on:click={submitCorrection}>
        {corrBusy ? '提交中…' : '提交更正'}
      </button>
      <button class="btn-ghost" on:click={() => (correctingId = null)}>关闭</button>
    </div>

    <h3 class="corr-history-title">更正历史（{target.correctionCount}）· 最新在前</h3>
    {#if target.corrections.length === 0}
      <p class="muted">暂无更正，有效粘度即原始取样值。</p>
    {:else}
      <table class="data-table corr-table">
        <thead>
          <tr><th>更正时间</th><th>更正后 Pa·s</th><th>原因</th></tr>
        </thead>
        <tbody>
          {#each target.corrections as c, i}
            <tr>
              <td>{c.correctedAt}{i === 0 ? ' · 有效' : ''}</td>
              <td class={i === 0 ? 'eff' : ''}>{c.viscosityPaS}</td>
              <td>{c.reason}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
{/if}

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
          <td class={row.correctionCount > 0 ? 'orig' : ''}>{row.originalViscosityPaS}</td>
          <td class="eff">{row.effectiveViscosityPaS}</td>
          <td>
            <button
              class="corr-badge"
              class:active={correctingId === row.id}
              on:click={() => openCorrection(row)}
            >
              {row.correctionCount} 次
            </button>
          </td>
          <td>{row.tempC ?? '—'}</td>
          <td>{row.notes || '—'}</td>
          <td class="ops">
            <button class="link-btn" on:click={() => edit(row)}>编辑</button>
            <button class="link-btn danger" on:click={() => remove(row.id)}>删除</button>
          </td>
        </tr>
      {:else}
        <tr><td colspan="9">暂无数据</td></tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  .eff {
    color: var(--vermillion-400);
    font-weight: 600;
  }

  .orig {
    color: var(--steel);
    text-decoration: line-through;
  }

  .corr-panel {
    border-top: 3px solid var(--vermillion-700);
  }

  .corr-history-title {
    margin-top: 1.2rem;
    font-size: 0.95rem;
    color: var(--paper);
  }

  .corr-table {
    margin-top: 0.5rem;
  }

  .corr-badge {
    background: none;
    border: 1px solid var(--line);
    color: var(--paper);
    padding: 0.1rem 0.5rem;
    font-size: 0.78rem;
    border-radius: 2px;
    cursor: pointer;
    white-space: nowrap;
  }

  .corr-badge:hover,
  .corr-badge.active {
    border-color: var(--vermillion-700);
    color: var(--vermillion-400);
  }

  input:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
</style>
