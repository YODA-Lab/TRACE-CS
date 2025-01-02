from pysat.formula import WCNF, CNF
from pysat.examples.optux import OptUx
from pysat.examples.lbx import LBX
from pysat.examples.rc2 import RC2
from collections import defaultdict
from pysat.examples.hitman import Hitman
from pysat.solvers import Solver


def get_vars(KB):
    variables = set()
    for c in KB:
        for l in c:
            variables.add(abs(l))
    return variables

def map_explanation(explanation, vpool):
	mapped_explanation = []
	for e in explanation:
		sub_e = [vpool.obj(i) for i in e if i>0 and vpool.obj(i)]
		mapped_explanation.extend(sub_e)
	return mapped_explanation



def get_MUS(public, private, q, vpool):
	# Compute a minimal unsatisfiable set
	wcnf2 = WCNF()
	if public:
		for c in public:
			wcnf2.append(c, weight=1)

	if private:
		for c in private:
			wcnf2.append(c, weight=100)


	wcnf2.extend((q.negate(topv=vpool.top).clauses))

	# wcnf2.extend(q)

	solver = OptUx(wcnf2)
	mus = solver.compute()
	expl  = [list(wcnf2.soft[m - 1]) for m in mus]
	return expl
	return map_explanation(expl, vpool)



def get_MCS(public, private, q, vpool):
	# Compute minimal hitting set
	wcnf = WCNF()
	if public:
		for c in public:
			wcnf.append(c, weight=1)

	if private:
		for c in private:
			wcnf.append(c, weight=100)

	# wcnf.extend(q.negate(topv=vpool.top).clauses)
	wcnf.extend(q)

	lbx = LBX(wcnf, use_cld=True, solver_name='g3')
	# Compute mcs and return the clauses indexes
	mcs = lbx.compute()
	return [list(wcnf.soft[m - 1]) for m in mcs]







def create_lookup_dict(clasues):
    idx_to_cls = defaultdict()
    cls_to_index = defaultdict()

    for i, label in enumerate(clasues):
        idx_to_cls[i + 1] = label
        cls_to_index[label] = i + 1
    return idx_to_cls, cls_to_index


def get_clauses_from_index(seed, clauses_dict):
    cls = []
    if seed:
        # seed = [item for sublist in seed for item in sublist]
        for s in seed:
            # print(s,'la')
            print("YO", clauses_dict[s])
            cls.extend(clauses_dict[s])
    return cls
def get_index_from_clauses(seed, clauses_dict):
	idx = []
	for s in seed:
		for key, val in clauses_dict.items():
			if val == s:
				idx.append(key)
	return idx





def SAT(KB1, KB2):
    s = Solver(name='g4')
    for k in KB1 + KB2:
        s.add_clause(k)
    if s.solve():
        return True
    else:
        return False


def skeptical_entailment(scheduler, KB, seed, q):
	# Check if KB entails a query
    s = Solver()
    for k in KB:
        s.add_clause(k)
    for k in seed:
        s.add_clause(k)
    # add negation of query

    s.append_formula(q.negate(topv=scheduler.vpool.top).clauses)
    if s.solve() == False:
        s.delete()
        return True
    else: 
        return False



def getMCS(KB, lits, query, seed): 
	
    wcnf = WCNF()
    
    # add seed as hard
    for s in seed:	
        wcnf.append(s)

    # add query as hard
    wcnf.extend(query)
    
    # add remaining clauses as soft
    for k in KB:
        if k not in seed:
            wcnf.append(k, weight=1)
    for l in lits:
        wcnf.append(l, weight=0)

    lbx = LBX(wcnf, solver_name='g4', use_cld=True, use_timer=True)
    mcs = lbx.compute()
    # print('MCS oracle time: {0:.4f}'.format(lbx.oracle_time()))
    
    if mcs:
        return [list(wcnf.soft[m - 1]) for m in mcs]
    else:
        return [[]]
    

def getMCS_MaxSAT(scheduler, KB, lits, query, seed):
    wcnf = WCNF()
    
    # add seed as hard
    for s in seed:	
        wcnf.append(s)

    # add query as hard
    wcnf.extend(query)

    for l in lits:
        wcnf.append(l)
    
    # add KB clauses as soft
    for k in KB:
        if k not in seed:
            wcnf.append(k, weight=5)
    
    RC = RC2(wcnf, solver='g4', adapt=True)
    model = RC.compute()

    mcs_KB = []
    for label in scheduler.templates:
        s = Solver("g3")
        s.append_formula(scheduler.templates[label])
        if not s.solve(assumptions = model):
            mcs_KB.extend(scheduler.templates[label])
            s.delete()
    return mcs_KB


def get_vars(KB):
    variables = set()
    for c in KB:
        for l in c:
            variables.add(abs(l))
    return variables


def explanation(scheduler, KB, lits, query):

    # idx2cls, cls2idx = create_lookup_dict(scheduler.templates)
    
    blocked = []
    R = Hitman(htype='maxsat')  # Reconciliation formula
    # wcnf = WCNF()
    # for c in KB:
    #     wcnf.append(c, weight=1)
    # for l in lits:
    #     wcnf.append(l, weight=1)
    # for q in query:
    #     wcnf.append(q)
    # MCS = LBX(wcnf, solver_name='g3')

    while True:
        seed = R.get()
        e_plus = []
        template_expl = []
        if seed == None:
            return "No explanation"
        for s in seed:
            e_plus.extend(scheduler.templates[s])
            template_expl.append(s)
      
        # print(seed)
        if SAT(e_plus, []) and not SAT(e_plus + lits, query):    
            # R.block(seed) # block the seed to generate a new explanation
            return template_expl
        else:
            mcs = getMCS(KB,lits, query, e_plus)
            # mcs = getMCS_MaxSAT(scheduler, KB, lits, query, e_plus)
            # Add all relevant clauses from scheduler to C
            if mcs != [[]]:
                relevant_clauses = add_relevant_clauses(scheduler, mcs)
                # C_indexed = [] 
                # for r in relevant_clauses:
                    # C_indexed.append(cls2idx[r])
                R.hit(relevant_clauses)


def add_relevant_clauses(scheduler, C):
    relevant_clauses = []
    for c in C:
        for label in scheduler.templates:
            if c in scheduler.templates[label]:
                if label not in relevant_clauses:
                    relevant_clauses.append(label)
    return relevant_clauses


def repair(KB, model):
    wcnf = WCNF()
    for c in KB:
        wcnf.append(c, weight = 1)
    wcnf.extend(model)
    MCS = LBX(wcnf, solver_name='CryptoMinisat')
    mcs = MCS.compute()
    mcs_clauses = [list(wcnf.soft[m - 1]) for m in mcs]
    new_KB = [c for c in KB if c not in mcs_clauses]
    new_KB.extend(model)
    return new_KB 
    