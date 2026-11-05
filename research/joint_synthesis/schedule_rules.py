"""Generate physical alternatives without accepting an architecture argument."""
from itertools import product
from .physical_plan import KernelPlan, Property, Schedule
from .requirements import PhysicalRequirements


def divisors(n):
    return tuple(i for i in range(1,n+1) if n%i==0)


def generate(graph,requirements=None):
    requirements=requirements or PhysicalRequirements();requirements.validate(graph)
    producer,consumer=graph.operators
    properties=tuple(Property(producer.output,l,s) for l,s in product(('row','col'),('sram','dram')))
    def schedules(op):
        return [Schedule(i,j,k,o) for i,j,k,o in product(divisors(op.left.rows),
            divisors(op.output.cols),divisors(op.left.cols),('ijk','ikj','jki'))]
    first=tuple(KernelPlan(producer,s,Property(producer.left,'row','dram'),p)
                for s,p in product(schedules(producer),properties)
                if requirements.producer_delivered is None or p in requirements.producer_delivered)
    second=tuple(KernelPlan(consumer,s,p,Property(consumer.output,'row','dram'))
                 for s,p in product(schedules(consumer),properties)
                 if requirements.consumer_required is None or p in requirements.consumer_required)
    return first,second
