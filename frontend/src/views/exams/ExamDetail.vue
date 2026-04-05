<template>
  <div class="exam-detail">
    <el-page-header @back="$router.back()" title="考试详情" />

    <el-card v-if="exam" class="exam-info" v-loading="loading">
      <template #header>
        <div class="card-header">
          <h2>{{ exam.title }}</h2>
          <el-tag v-if="exam.is_published" type="success">已发布</el-tag>
          <el-tag v-else type="info">未发布</el-tag>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="描述">{{ exam.description || '无' }}</el-descriptions-item>
        <el-descriptions-item label="考试时长">{{ exam.duration_minutes }} 分钟</el-descriptions-item>
        <el-descriptions-item label="总分">{{ exam.total_score }} 分</el-descriptions-item>
        <el-descriptions-item label="及格分数">{{ exam.pass_score }} 分</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatDate(exam.start_time) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ formatDate(exam.end_time) }}</el-descriptions-item>
      </el-descriptions>

      <div class="exam-actions" v-if="exam.is_published">
        <el-button type="primary" size="large" @click="startExam">
          参加考试
        </el-button>
      </div>
    </el-card>

    <el-card class="questions-list" v-if="questions.length > 0">
      <template #header>
        <div class="card-header">
          <span>题目列表</span>
          <span>共 {{ questions.length }} 题</span>
        </div>
      </template>

      <div v-for="(question, index) in questions" :key="question.id" class="question-item">
        <div class="question-header">
          <span class="question-number">第 {{ index + 1 }} 题</span>
          <el-tag size="small" :type="getQuestionTypeTag(question.type)">
            {{ getQuestionTypeLabel(question.type) }}
          </el-tag>
          <span class="question-score">{{ question.score }} 分</span>
        </div>
        <div class="question-content">{{ question.content }}</div>
        <div v-if="question.options && question.options.length > 0" class="question-options">
          <div v-for="(option, optIndex) in question.options" :key="optIndex" class="option-item">
            {{ String.fromCharCode(65 + optIndex) }}. {{ option }}
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { examApi, questionApi, submissionApi } from '@/api'

const route = useRoute()
const router = useRouter()
const examId = route.params.id

const loading = ref(false)
const exam = ref(null)
const questions = ref([])

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const getQuestionTypeLabel = (type) => {
  const types = {
    single_choice: '单选题',
    multiple_choice: '多选题',
    true_false: '判断题',
    fill_blank: '填空题',
    short_answer: '简答题'
  }
  return types[type] || type
}

const getQuestionTypeTag = (type) => {
  const tags = {
    single_choice: 'primary',
    multiple_choice: 'success',
    true_false: 'warning',
    fill_blank: 'info',
    short_answer: 'danger'
  }
  return tags[type] || ''
}

const loadExam = async () => {
  loading.value = true
  try {
    exam.value = await examApi.getDetail(examId)
    questions.value = await questionApi.getList(examId)
  } catch (error) {
    ElMessage.error('加载考试详情失败')
  } finally {
    loading.value = false
  }
}

const startExam = async () => {
  try {
    await submissionApi.startExam(examId)
    router.push(`/exams/${examId}/take`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '开始考试失败')
  }
}

onMounted(() => {
  loadExam()
})
</script>

<style scoped>
.exam-detail {
  padding: 20px;
}

.exam-info {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
}

.exam-actions {
  margin-top: 20px;
  text-align: center;
}

.questions-list {
  margin-top: 20px;
}

.question-item {
  padding: 16px;
  border-bottom: 1px solid #ebeef5;
}

.question-item:last-child {
  border-bottom: none;
}

.question-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.question-number {
  font-weight: bold;
}

.question-score {
  color: #f56c6c;
  font-weight: bold;
}

.question-content {
  margin-bottom: 12px;
  line-height: 1.6;
}

.question-options {
  padding-left: 20px;
}

.option-item {
  padding: 8px 0;
  color: #606266;
}
</style>
