import { reactive } from 'vue';
import type { FormStateStore } from './project';

export const formState: FormStateStore = reactive({
    isCorrectDrive: null,
    areProjectDetailsCorrect: null,
    project: null,
    dataClassification: null,
    retentionPeriod: null
});