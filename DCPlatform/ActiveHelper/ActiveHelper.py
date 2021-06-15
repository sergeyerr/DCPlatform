import pandas as pd
from ActiveHelper.TaskSelector import get_emb, get_task_type
from ActiveHelper.ColumnChecker import check_column_feasibility
from ActiveHelper.ColumnSelector import get_columns_in_query
from ActiveHelper.MethodsSuggester import suggest_methods
from ActiveHelper.OntologyRecomender import find_methods_for_task
from scipy.spatial import distance
from openml.tasks import TaskType


class ActiveHelper(object):
    def __init__(self):
        self.data = None
        self.reset()

    def reset(self):
        self.current_state = self.state_0
        self.greeting = True
        # self.stack = []
       # self.data = None
        self.task = None
        self.superv = None
        self.target_col = None
        self.possible_targets = set(pd.read_csv('ActiveHelper/target_list.csv')['target'].str.lower().values.reshape(-1))
        self.task_query = None
        self.keywords = {'Начать заново': (self.state_0, get_emb('начать заново')),
                         'В начало диалога': (self.state_0, get_emb('в начало диалога'))
                         }
        #      'Назад' : ,
        #   'К выбору задачи' :,
        #    'К загрузке данных' :
        #    'К выбору целевой колонки' : ,}

    def check_keywords(self, query):
        target = get_emb(str.lower(query))
        for k in self.keywords:
            if distance.cosine(target, self.keywords[k][1]) < 0.2:
                print(k, distance.cosine(target, self.keywords[k][1]))
                return self.keywords[k][0](query, reset=True)
        return None

    # def _back_(self):
    #  if len(stack) == 0:
    #     return 'Вы ещё не совершали операций'
    #  self.data, self.task, self.superv, self.target_col, self.task_query =

    # def _to_task_(self)

    def confirmation_state(self, positive_state=None, negative_state=None, threshold=0.225):
        if positive_state is None or negative_state is None:
            raise Exception('invalid clause')
        def tmp_confirmation(query):
            # = ['Да', 'Верно', 'Ок', 'ага']
            #negative_vars = ['Нет', 'Неправильно', 'Заново', 'косячно']
            #pos = get_columns_in_query(query, positive_vars, threshold=1, norm=True)
            #neg = get_columns_in_query(query, negative_vars, threshold=1, norm=True)
            positive_emb = get_emb('да, правильно')
            negative_emb = get_emb('нет, не правильно')
            target = get_emb(query)
            pos_dist = distance.cosine(target, positive_emb)
            neg_dist = distance.cosine(target, negative_emb)
            print(pos_dist, neg_dist)
            #if len(pos) == 0 and len(neg) == 0:
            if neg_dist > threshold and pos_dist > threshold:
                return 'Не удалось распознать ответ. Пожалуйста, повторите его'
            #if (2 if len(pos) == 0 else pos[0][1]) > (2 if len(neg) == 0 else neg[0][1]):
            if pos_dist > neg_dist:
                return negative_state(None)
            else:
                return positive_state(None)

        return tmp_confirmation

    def state_0(self, query, reset=False):
        res = ''
        if reset:
            self.reset()
        if self.greeting:
            res += 'Доброго времени суток! \n'
            self.greeting = False
        self.current_state = self.state_task_selection
        res += 'Пожалуйста, опишите задачу, которую хотите решить.'
        return res

    def state_task_selection(self, query: str):
        task_type, desc = get_task_type(query)
        if task_type == None:
            return 'Простите, я не могу определить задачу. Перефразируйте, пожалуйста, вопрос.'
        res = 'Я считаю, что вы хотите решить задачу '
        if task_type == TaskType.SUPERVISED_CLASSIFICATION:
            self.current_state = self.state_plea_to_upload_data
            res += 'классификации.'
            self.superv = True
        elif task_type == TaskType.SUPERVISED_REGRESSION:
            self.current_state = self.state_plea_to_upload_data
            res += 'регрессии.'
            self.superv = True
        elif task_type == TaskType.CLUSTERING:
            self.current_state = self.state_plea_to_upload_data
            res += 'кластеризации.'
            self.superv = False
        else:
            raise Exception('Wrong Task for task selection')

        self.task = task_type
        self.task_query = query
        # вот тут развилка для умных пользователей
        target_col = None
        if self.data is not None:
            target_col = self._find_target_cols_in_history()
        if target_col is not None:
            res += f' Также я предполагаю, что вы хотите определять колонку {target_col}. '
            def positive_state(query):
                self.target_col = target_col
                return self.state_find_algos(query)

            self.current_state = self.confirmation_state(positive_state, self.state_after_guess_task_confirmation)
        else:
            self.current_state = self.confirmation_state(self.state_plea_to_upload_data, self.state_0)
        res += ' \nВсё правильно? \n\n' + desc
        return res


    def state_after_guess_task_confirmation(self, query):
        if self.data is None:
            raise Exception('this state should be preceded by task selection with data, wtf')

        self.current_state = self.confirmation_state(self.state_plea_to_specify_target_col, self.state_0)
        return 'А задачу-то я угадал?'


    def state_plea_to_upload_data(self, query: str):
        if self.data is not None:
            return self.state_check_data_download(None)
        self.current_state = self.state_check_data_download
        return 'Загрузите, пожалуйста, данные. Это можно сделать с помощью кнопки upload data.'

    def state_check_data_download(self, query: str):
        if self.data is None:
            return 'Данные не удалось распознать. Пожалуйста, загрузите их в формате .csv и кодировке utf-8.'
        else:
            if self.superv:
                return self.state_try_extract_target_col(None)
            else:
                return self.state_find_algos(None)


    def _find_target_cols_in_history(self):
        # поиск в предыдущем запросе таргета
        found_cols = get_columns_in_query(self.task_query, [x for x in self.data.columns if len(x) > 3])
        if len(found_cols) != 0:
            cols = [x[0] for x in found_cols]
            for col in cols:
                if self.task in check_column_feasibility(self.data[col]):
                    return col
        # поиск таргета среди истории
        possible_targs_ = set(self.data.columns.str.lower()).intersection(self.possible_targets)
        possible_targs = set()
        for col in self.data.columns:
            if str.lower(col) in possible_targs_:
                possible_targs.add(col)
        for col in possible_targs:
            if self.task in check_column_feasibility(self.data[col]):
                return col
        return None

    def state_try_extract_target_col(self, query=None):
        if self.task_query is not None:
            col = self._find_target_cols_in_history()
            if col:
                def positive_state(query):
                    self.target_col = col
                    return self.state_find_algos(query)

                self.current_state = self.confirmation_state(positive_state, self.state_plea_to_specify_target_col)
                return f'Я предполагаю, что вы хотите определять колонку {col}. Я прав?'
            else:
                return self.state_plea_to_specify_target_col(query)
        else:
            raise Exception('why task query is None?? ')

    def state_plea_to_specify_target_col(self, query: str):
        # if self.target_col is not None:
        #  print('fix plea')
        # return state_find_target_col()
        # if query is not None:

        # else:
        self.current_state = self.state_find_target_col
        return 'Пожалуйста, напишите целевую колонку, которую хотите научится определять'

    def state_find_target_col(self, query: str):
        if query != None:
            found_cols = get_columns_in_query(query, list(self.data.columns))
            if len(found_cols) == 0:
                return 'Не удалось найти упоминание колонки в запросе. Проверьте название колонки'
            else:
                cols = [x[0] for x in found_cols]
                for col in cols:
                    if self.task in check_column_feasibility(self.data[col]):
                        def positive_state(query):
                            self.target_col = col
                            return self.state_find_algos(query)

                        self.current_state = self.confirmation_state(positive_state,
                                                                     self.state_plea_to_specify_target_col)
                        return f'Я считаю, что Вы хотите определять колонку {col}. Я прав?'
                return f'Ни одна из колонок {",".join(cols)}\n не подходит под выбранную задачу. \nПожалуйста,' \
                       f'проверьте запрос или данные '

    def state_find_algos(self, query: str):
        if self.task is None:
            raise Exception('No task selected')
        if self.data is None:
            raise Exception('No dataset selected')
        if self.superv and self.target_col == None:
            raise Exception('No target col selected')
        methods = suggest_methods(self.task, self.data, self.target_col)
        methods = [x[0] for x in methods]
        ont_methods = find_methods_for_task(self.task)
        res = ''
        if len(methods) == 0 and len(ont_methods) == 0:
            return 'Не удаётся найти подходящие методы для вашей задачи. Если данное сообщение вылезло в данной ' \
                   'версии помощника, напиши автору '
        if len(methods) != 0:
            methods_str = "\n".join(methods[:3])
            res = f'Эти методы должны хорошо работать на ваших данных:\n {methods_str}'
            if len(ont_methods) > 0:
                res += '\n Также, '
            # return 'В системе нет подходящих методов под задачу'
        if len(ont_methods) != 0:
            ont_methods = list(set(ont_methods) - set(methods))
            methods_str = "\n".join(ont_methods[:3])
            res += f'Я предлагаю Вам попробовать алгоритмы:\n\n {methods_str}'
        self.current_state = self.end_state
        return res

    def end_state(self, query: str):
        return 'Если хотите начать заново, напишите "заново". В следующих версиях можно будет вернутся к предыдущим шагам.'

    def process_query(self, query: str) -> list:
        tmp_res = self.check_keywords(str.lower(query))
        if tmp_res is None:
            return [['text', self.current_state(str.lower(query))], ['text', 'Здоровенная шлёпа']]
        return [['text', tmp_res]]

