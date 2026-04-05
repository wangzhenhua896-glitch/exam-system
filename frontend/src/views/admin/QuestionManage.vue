<template>
  <div class="question-manage">
    <el-page-header @back="$router.back()" title="题目管理" />

    <el-card class="question-list">
      <template #header>
        <div class="card-header">
          <span>{{ exam?.title }} - 题目列表</span>
          <el-button type="primary" @click="showCreateDialog = true">添加题目</el-button>
        </div>
      </template>

      <el-table :data="questions" style="width: 100%" v-loading="loading">
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="content" label="题目内容" show-overflow-tooltip />
        <el-table-column prop="type" label="题型" width="120">
          <template #default="{ row }">
            <el-tag :type="getQuestionTypeTag(row.type)">{{ getQuestionTypeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="分值" width="80" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="warning" size="small" @click="editQuestion(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="deleteQuestion(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="questions.length === 0 && !loading" description="暂无题目" />
    </el-card>

    <!-- 创建/编辑题目对话框 -->
    <el-dialog v-model="showCreateDialog" :title="isEditing ? '编辑题目' : '添加题目'" width="700px">
      <el-form :model="questionForm" label-width="100px">
        <el-form-item label="题型">
          <el-select v-model="questionForm.type" style="width: 100%">
            <el-option label="单选题" value="single_choice" />
            <el-option label="多选题" value="multiple_choice" />
            <el-option label="判断题" value="true_false" />
            <el-option label="填空题" value="fill_blank" />
            <el-option label="简答题" value="short_answer" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目内容">
          <el-input v-model="questionForm.content" type="textarea" :rows="3" placeholder="请输入题目内容" />
        </el-form-item>
        <el-form-item label="选项" v-if="['single_choice', 'multiple_choice'].includes(questionForm.type)">
          <div v-for="(option, index) in questionForm.options" :key="index" class="option-row">
            <span class="option-label">{{ String.fromCharCode(65 + index) }}.</span>
            <el-input v-model="questionForm.options[index]" placeholder="选项内容" />
            <el-button type="danger" circle size="small" @click="removeOption(index)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <el-button type="primary" @click="addOption" size="small">添加选项</el-button>
        </el-form-item>
        <el-form-item label="正确答案">
          <el-input v-if="questionForm.type === 'short_answer' || questionForm.type === 'fill_blank'" v-model="questionForm.correct_answer" type="textarea" :rows="2" placeholder="请输入正确答案" />
          <el-select v-else-if="questionForm.type === 'true_false'" v-model="questionForm.correct_answer">
            <el-option label="正确" value="true" />
            <el-option label="错误" value="false" />
          </el-select>
          <el-select v-else v-model="questionForm.correct_answer">
            <el-option v-for="(opt, index) in questionForm.options" :key="index" :label="String.fromCharCode(65 + index)" :value="String.fromCharCode(65 + index)" />
          </el-select>
        </el-form-item>
        <el-form-item label="分值"><el-input-number v-model="questionForm.score" :min="1" :max="100" /></el-form-item>
        <el-form-item label="评分标准" v-if="questionForm.type === 'short_answer'">
          <el-input v-model="questionForm.scoring_criteria" type="textarea" :rows="3" placeholder="请输入AI评分标准" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveQuestion" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { examApi, questionApi } from '@/api'

const route = useRoute()
const examId = route.params.examId

const loading = ref(false)
const saving = ref(false)
const exam = ref(null)
const questions = ref([])
const showCreateDialog = ref(false)
const isEditing = ref(false)
const editingId = ref(null)

const questionForm = ref({ type: 'single_choice', content: '', options: ['', '', '', ''], correct_answer: '', score: 10, scoring_criteria: '' })

const getQuestionTypeLabel = (type) => {
  const types = { single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', fill_blank: '填空题', short_answer: '简答题' }
  return types[type] || type
}

const getQuestionTypeTag = (type) => {
  const tags = { single_choice: 'primary', multiple_choice: 'success', true_false: 'warning', fill_blank: 'info', short_answer: 'danger' }
  return tags[type] || ''
}

const addOption = () => { questionForm.value.options.push('') }
const removeOption = (index) => { questionForm.value.options.splice(index, 1) }

const loadData = async () => {
  loading.value = true
  try {
    exam.value = await examApi.getDetail(examId)
    questions.value = await questionApi.getList(examId)
  } catch { ElMessage.error('加载失败') } 
  finally { loading.value = false }
}

const editQuestion = (question) => {
  isEditing.value = true
  editingId.value = question.id
  questionForm.value = { ...question, options: question.options || ['', '', '', ''] }
  showCreateDialog.value = true
}

const saveQuestion = async () => {
  saving.value = true
  try {
    const data = { ...questionForm.value, exam_id: parseInt(examId) }
    if (isEditing.value) await questionApi.update(editingId.value, data)
    else await questionApi.create(data)
    ElMessage.success('保存成功')
    showCreateDialog.value = false
    resetForm()
    loadData()
  } catch (error) { ElMessage.error(error.response?.data?.detail || '保存失败') } 
  finally { saving.value = false }
}

const deleteQuestion = async (question) => {
  try {
    await ElMessageBox.confirm('确定删除该题目？', '提示', { type: 'warning' })
    await questionApi.delete(question.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) { if (error !== 'cancel') ElMessage.error('删除失败') }
}

const resetForm = () => {
  questionForm.value = { type: 'single_choice', content: '', options: ['', '', '', ''], correct_answer: '', score: 10, scoring_criteria: '' }
  isEditing.value = false
  editingId.value = null
}

onMounted(() => { loadData() })
</script>

<style scoped>
.question-manage { padding: 20px; }
.question-list { margin-top: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.option-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.option-label { width: 30px; }
</style>
