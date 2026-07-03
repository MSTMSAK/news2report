<template>
  <el-card class="daily-report-card">
    <template #header>
      <div class="card-header">
        <span>📊 AI 领域日报</span>
        <div class="header-actions">
          <el-tag v-if="report?.date" type="info" size="small">{{ report.date }}</el-tag>
          <el-button
            type="primary"
            size="small"
            :loading="loading"
            @click="fetchReport(true)"
          >
            {{ loading ? '生成中...' : '重新生成' }}
          </el-button>
        </div>
      </div>
    </template>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      show-icon
      class="report-alert"
    />

    <div v-if="loading && !report" class="loading-wrapper">
      <el-skeleton :rows="10" animated />
    </div>

    <div v-else-if="report?.html" class="report-content" v-html="report.html"></div>

    <el-empty v-else description="暂无日报，点击上方按钮生成"></el-empty>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface DailyReport {
  status: string
  date: string
  markdown: string
  html: string
  generated_at: string
  path: string
}

const report = ref<DailyReport | null>(null)
const loading = ref(false)
const error = ref('')

async function fetchReport(force = false) {
  loading.value = true
  error.value = ''
  try {
    const url = force ? '/api/daily-report/generate?force=true' : '/api/daily-report'
    const response = await fetch(url, force ? { method: 'POST' } : undefined)
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || '获取日报失败')
    }
    report.value = data
  } catch (err: any) {
    error.value = err.message || '获取日报失败'
    console.error('获取日报失败:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchReport(false)
})

defineExpose({
  fetchReport,
})
</script>

<style scoped>
.daily-report-card {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.report-alert {
  margin-bottom: 16px;
}

.loading-wrapper {
  padding: 20px;
}

.report-content {
  font-size: 14px;
  line-height: 1.8;
  color: #1a1a1a;
}

.report-content :deep(h1) {
  font-size: 22px;
  font-weight: 600;
  margin: 24px 0 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid #409eff;
}

.report-content :deep(h2) {
  font-size: 18px;
  font-weight: 600;
  margin: 24px 0 12px;
  color: #1a1a1a;
}

.report-content :deep(h3) {
  font-size: 15px;
  font-weight: 600;
  margin: 16px 0 8px;
  color: #333333;
}

.report-content :deep(p) {
  margin: 8px 0;
}

.report-content :deep(ul),
.report-content :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.report-content :deep(li) {
  margin: 6px 0;
}

.report-content :deep(hr) {
  border: none;
  border-top: 1px solid #e4e7ed;
  margin: 20px 0;
}

.report-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.report-content :deep(th),
.report-content :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 8px 12px;
  text-align: left;
}

.report-content :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
}

.report-content :deep(blockquote) {
  border-left: 4px solid #409eff;
  padding-left: 12px;
  margin: 12px 0;
  color: #606266;
}

.report-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', monospace;
  font-size: 13px;
}

.report-content :deep(pre) {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}
</style>
