<template>
  <div class="my-exams">
    <el-card>
      <template #header>
        <span>我的考试记录</span>
      </template>

      <el-table :data="submissions" style="width: 100%" v-loading="loading">
        <el-table-column prop="exam.title" label="考试名称" />
        <el-table-column prop="started_at" label="开始时间" width="180">
          <template #default="{ row }">{{ formatDate(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="submitted_at" label="提交时间" width="180">
          <template #default="{ row }">{{ formatDate(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column prop="total_score" label="得分" width="100">
          <template #default="{ row }">{{ row.total_score }} / {{ row.max_score }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="submissions.length === 0 && !loading" description="暂无考试记录" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { submissionApi } from '@/api'

const loading = ref(false)
const submissions = ref([])

const formatDate = (date) => date ? new Date(date).toLocaleString('zh-CN') : '-'

const getStatusLabel = (status) => {
  const labels = { in_progress: '进行中', submitted: '已提交', grading: '批改中', completed: '已完成' }
  return labels[status] || status
}

const getStatusType = (status) => {
  const types = { in_progress: 'warning', submitted: 'primary', grading: 'info', completed: 'success' }
  return types[status] || ''
}

const loadSubmissions = async () => {
  loading.value = true
  try {
    submissions.value = await submissionApi.getMyList()
  } catch (error) {
    ElMessage.error('加载考试记录失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => { loadSubmissions() })
</script>

<style scoped>
.my-exams { padding: 20px; }
</style>
