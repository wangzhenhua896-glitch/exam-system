<template>
  <div class="take-exam">
    <el-card v-if="exam" class="exam-header">
      <div class="exam-title">
        <h2>{{ exam.title }}</h2>
        <div class="exam-timer">
          <el-icon><Timer /></el-icon>
          <span :class="{ 'warning': remainingTime < 300 }">剩余时间: {{ formatTime(remainingTime) }}</span>
        </div>
      </div>
    </el-card>

    <div v-if="questions.length > 0" class="questions-container">
      <el-card v-for="(question, index) in questions" :key="question.id" class="question-card">
        <div class="question-header">
          <span class="question-number">第 {{ index + 1 }} 题</span>
          <el-tag size="small" :type="getQuestionTypeTag(question.type)">
            {{ getQuestionTypeLabel(question.type) }}
          </el-tag>
          <span class="question-score">{{ question.score }} 分</span>
        </div>

        <div class="question-content">{{ question.content }}</div>

        <!-- 单选题 -->
        <el-radio-group v-if="question.type === 'single_choice'" v-model="answers[question.id]" class="question-answer">
          <el-radio v-for="(option, optIndex) in question.options" :key="optIndex" :label="String.fromCharCode(65 + optIndex)">
            {{ String.fromCharCode(65 + optIndex) }}. {{ option }}
          </el-radio>
        </el-radio-group>

        <!-- 多选题 -->
        <el-checkbox-group v-else-if="question.type === 'multiple_choice'" v-model="answers[question.id]" class="question-answer">
          <el-checkbox v-for="(option, optIndex) in question.options" :key="optIndex" :label="String.fromCharCode(65 + optIndex)">
            {{ String.fromCharCode(65 + optIndex) }}. {{ option }}
          </el-checkbox>
        </el-checkbox-group>

        <!-- 判断题 -->
        <el-radio-group v-else-if="question.type === 'true_false'" v-model="answers[question.id]" class="question-answer">
          <el-radio label="true">正确</el-radio>
          <el-radio label="false">错误</el-radio>
        </el-radio-group>

        <!-- 填空题/简答题 -->
        <el-input v-else v-model="answers[question.id]" type="textarea" :rows="4" placeholder="请输入答案" class="question-answer" />
      </el-card>

      <div class="submit-section">
        <el-button type="primary" size="large" @click="submitExam">提交试卷</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { examApi, questionApi, submissionApi } from '@/api'

const route = useRoute()
const router = useRouter()
const examId = route.params.id

const loading = ref(false)
const exam = ref(null)
const questions = ref([])
const answers = ref({})
const submissionId = ref(null)
const remainingTime = ref(0)
let timer = null

const formatTime = (seconds) => {
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

const getQuestionTypeLabel = (type) => {
  const types = { single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', fill_blank: '填空题', short_answer: '简答题' }
  return types[type] || type
}

const getQuestionTypeTag = (type) => {
  const tags = { single_choice: 'primary', multiple_choice: 'success', true_false: 'warning', fill_blank: 'info', short_answer: 'danger' }
  return tags[type] || ''
}

const startTimer = () => {
  timer = setInterval(() => {
    if (remainingTime.value > 0) {
      remainingTime.value--
    } else {
      clearInterval(timer)
      ElMessage.warning('考试时间到，自动提交')
      submitExam()
    }
  }, 1000)
}

const loadExam = async () => {
  loading.value = true
  try {
    exam.value = await examApi.getDetail(examId)
    questions.value = await questionApi.getList(examId)
    const submission = await submissionApi.startExam(examId)
    submissionId.value = submission.id
    remainingTime.value = exam.value.duration_minutes * 60
    startTimer()
  } catch (error) {
    ElMessage.error('加载考试失败')
    router.push('/exams')
  } finally {
    loading.value = false
  }
}

const submitExam = async () => {
  try {
    await ElMessageBox.confirm('确定要提交试卷吗？提交后将无法修改', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    
    for (const question of questions.value) {
      let answer = answers.value[question.id]
      if (Array.isArray(answer)) answer = answer.join(',')
      if (answer) await submissionApi.submitAnswer(submissionId.value, { question_id: question.id, answer_content: answer })
    }
    
    await submissionApi.submitExam(submissionId.value)
    clearInterval(timer)
    ElMessage.success('试卷提交成功')
    router.push('/my-exams')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('提交失败')
  }
}

onMounted(() => { loadExam() })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.take-exam { padding: 20px; }
.exam-header { margin-bottom: 20px; }
.exam-title { display: flex; justify-content: space-between; align-items: center; }
.exam-title h2 { margin: 0; }
.exam-timer { display: flex; align-items: center; gap: 8px; font-size: 18px; }
.exam-timer .warning { color: #f56c6c; font-weight: bold; }
.questions-container { display: flex; flex-direction: column; gap: 20px; }
.question-card { margin-bottom: 0; }
.question-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.question-number { font-weight: bold; }
.question-score { color: #f56c6c; font-weight: bold; }
.question-content { margin-bottom: 16px; line-height: 1.6; font-size: 16px; }
.question-answer { display: flex; flex-direction: column; gap: 12px; }
.submit-section { text-align: center; margin-top: 20px; }
</style>
