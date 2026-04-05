<template>
  <div class="exam-manage">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>考试管理</span>
          <el-button type="primary" @click="showCreateDialog = true">创建考试</el-button>
        </div>
      </template>

      <el-table :data="exams" style="width: 100%" v-loading="loading">
        <el-table-column prop="title" label="考试名称" />
        <el-table-column prop="start_time" label="开始时间" width="180">
          <template #default="{ row }">{{ formatDate(row.start_time) }}</template>
        </el-table-column>
        <el-table-column prop="is_published" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_published ? 'success' : 'info'">{{ row.is_published ? '已发布' : '未发布' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="manageQuestions(row)">题目管理</el-button>
            <el-button type="warning" size="small" @click="editExam(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="deleteExam(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showCreateDialog" :title="isEditing ? '编辑考试' : '创建考试'" width="600px">
      <el-form :model="examForm" label-width="100px">
        <el-form-item label="考试名称"><el-input v-model="examForm.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="examForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="开始时间"><el-date-picker v-model="examForm.start_time" type="datetime" style="width: 100%" /></el-form-item>
        <el-form-item label="结束时间"><el-date-picker v-model="examForm.end_time" type="datetime" style="width: 100%" /></el-form-item>
        <el-form-item label="考试时长"><el-input-number v-model="examForm.duration_minutes" :min="1" /> 分钟</el-form-item>
        <el-form-item label="总分"><el-input-number v-model="examForm.total_score" :min="1" /> 分</el-form-item>
        <el-form-item label="及格分数"><el-input-number v-model="examForm.pass_score" :min="0" /> 分</el-form-item>
        <el-form-item label="发布"><el-switch v-model="examForm.is_published" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveExam" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { examApi } from '@/api'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const exams = ref([])
const showCreateDialog = ref(false)
const isEditing = ref(false)
const editingId = ref(null)

const examForm = ref({ title: '', description: '', start_time: null, end_time: null, duration_minutes: 60, total_score: 100, pass_score: 60, is_published: false })

const formatDate = (date) => date ? new Date(date).toLocaleString('zh-CN') : '-'

const loadExams = async () => {
  loading.value = true
  try { exams.value = await examApi.getList() } 
  catch { ElMessage.error('加载失败') } 
  finally { loading.value = false }
}

const manageQuestions = (exam) => { router.push(`/admin/questions/${exam.id}`) }

const editExam = (exam) => {
  isEditing.value = true
  editingId.value = exam.id
  examForm.value = { ...exam }
  showCreateDialog.value = true
}

const saveExam = async () => {
  saving.value = true
  try {
    if (isEditing.value) await examApi.update(editingId.value, examForm.value)
    else await examApi.create(examForm.value)
    ElMessage.success('保存成功')
    showCreateDialog.value = false
    resetForm()
    loadExams()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

const deleteExam = async (exam) => {
  try {
    await ElMessageBox.confirm('确定删除该考试？', '提示', { type: 'warning' })
    await examApi.delete(exam.id)
    ElMessage.success('删除成功')
    loadExams()
  } catch (error) { if (error !== 'cancel') ElMessage.error('删除失败') }
}

const resetForm = () => {
  examForm.value = { title: '', description: '', start_time: null, end_time: null, duration_minutes: 60, total_score: 100, pass_score: 60, is_published: false }
  isEditing.value = false
  editingId.value = null
}

onMounted(() => { loadExams() })
</script>

<style scoped>
.exam-manage { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
